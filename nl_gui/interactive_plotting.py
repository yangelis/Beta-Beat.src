#!/afs/cern.ch/work/o/omc/anaconda/bin/python

from __future__ import print_function
import sys, os
import numpy as np
import argparse
import matplotlib.pyplot as plt

import matplotlib
matplotlib.style.use('ggplot')

from matplotlib.lines import Line2D
from matplotlib.artist import Artist
from matplotlib.mlab import dist_point_to_segment
from matplotlib.axes import Axes
from matplotlib.patches import Polygon
import matplotlib.dates as mdates
import pandas as pd    
from data_loader import load_csv 
from datetime import datetime
from datetime import timedelta 
from time import mktime
from polygon_interacter import PolygonInteractor 


class IteratePlatteauPlots(object):
    '''
    Author: Felix Carlier
    
    IteratePlatteau class to iterate through the crossing (xing) angle scans for nonlinear corrections.
    The main purpose here is to graphically represent the data and the guessed platteaus from the automatic 
    platteau detection module. The platteaus are plotted as green vertical spans (axvspan) and are animated through
    the PolygonInteractor class, allowing changes to be made to the platteau selection. 
      
      DataFrames:
      - currents_df  : extracted currents from Timber of 
      - orbit_df     : extraced orbit data from Timber. Only rms orbits are plotted for now, 
                       though more available in dataframe
      - platteaus_df : dataframe of initial guessed platteaus. (end knob trim, start platteau, end platteau)
      
      Axes:
      - self.axes : contains all matplotlib axes in dictionary format with keys describing positions

    '''
    def __init__(self, filenames, output_platteau_file):
        self.output_platteau_file = output_platteau_file 
        self.currents_df  = load_csv(filenames[0], filetype='currents')
        self.orbit_df     = load_csv(filenames[1], filetype='orbit')
        self.platteaus_df = load_csv(filenames[2], filetype='platteaus')
        self.currents_df = self._normalize_data(self.currents_df)
        print('Data imported.')
        self.accepted_plat = pd.DataFrame(index=np.arange(len(self.platteaus_df['knob_plat'])), columns=['B1_min','B1_max','B2_min','B2_max',])
        self.idx = 0 

        self.fig = plt.figure(figsize=(18,18))
        self.fig.patch.set_facecolor('white')
        self.fig.canvas.mpl_connect('key_press_event', self._next_plat_key)
        self.fig.canvas.mpl_connect('button_press_event', self._assign_click_to_poly)

        ax1 = self.fig.add_subplot(321)
        ax3 = self.fig.add_subplot(323, sharex=ax1)
        ax5 = self.fig.add_subplot(325, sharex=ax1)
        ax2 = self.fig.add_subplot(322)
        ax4 = self.fig.add_subplot(324, sharex=ax2)
        ax6 = self.fig.add_subplot(326, sharex=ax2)
        self.axes = {'top_left': ax1, 'top_right':ax2, 'middle_left':ax3, 
                     'middle_right':ax4, 'bottom_left':ax5, 'bottom_right':ax6}
        
        self._get_plat_times()
        self._make_plot()
        self.all_poly = self._make_all_poly()
        self._update_span()
        plt.show()
    
    def _make_all_poly(self):
        ''' Create a dictionary of axvspan Polygons to be plotted on all axes'''
        all_poly = {} 
        for key in self.axes:
            span_temp = self.axes[key].axvspan(0,0, facecolor='g', alpha=0.2, animated=True)
            all_poly[key] = PolygonInteractor(self.axes[key], span_temp)
        return all_poly
    
    def _assign_click_to_poly(self, event):
        level_plots = ['top_', 'middle_', 'bottom_']
        for side in ('left', 'right'):
            keys = [key + side for key in level_plots]
            axes = [self.axes[key] for key in keys]
            if event.inaxes in axes:
                for key in keys:
                    self.all_poly[key].button_press_callback(event)
            
    def _get_previous_platteau_idx(self):
        ''' Iterate through the guessed platteau times to define new plotting xlimits and platteau limits. '''
        self.idx += -1 
        self._get_plat_times()
        self.new_limits_B1 = [self.accepted_plat.loc[self.idx,'B1_min'], self.accepted_plat.loc[self.idx,'B1_max']]
        self.new_limits_B2 = [self.accepted_plat.loc[self.idx,'B2_min'], self.accepted_plat.loc[self.idx,'B2_max']]

    def _get_next_platteau_idx(self):
        ''' Iterate through the guessed platteau times to define new plotting xlimits and platteau limits. '''
        self.idx += 1 
        self._get_plat_times()

    def _get_plat_times(self):
        self.time_knob = self.platteaus_df['knob_plat'][self.idx]-timedelta(seconds=50)
        self.time_min_pl = self.platteaus_df['data_plat_start'][self.idx]
        self.time_max_pl = self.platteaus_df['data_plat_end'][self.idx]
        self.time_max = self.time_max_pl+timedelta(seconds=50)
        self.new_limits_B1 = [self.time_min_pl, self.time_max_pl]
        self.new_limits_B2 = [self.time_min_pl, self.time_max_pl]

    def _next_plat_key(self, event):
        '''
        Defines actions on (n)-key press. 
        1) Append accepted platteau values to platteau lists for B1 and B2
        2) Try: Get next platteau times, update spans and clear plots, generate data plots
        '''
        if event.key == 'n':
            self._get_span_limits()
            self.accepted_plat.loc[self.idx] = self.new_limits_B1[0], self.new_limits_B1[1], self.new_limits_B2[0], self.new_limits_B2[1]
            try:
                self._get_next_platteau_idx()
                self._clear_plots()
                self._make_plot()
            except KeyError:
                print('Last platteau analysed, no more platteaus. Continue to data cleaning.') 
                self.accepted_plat.to_csv(self.output_platteau_file)
                plt.close()
        elif event.key == 'p':
            try:
                self._get_previous_platteau_idx()
                self._clear_plots()
                self._make_plot()
            except KeyError:
                wurstel

    def _clear_plots(self):
        '''Updates vertical spans and clears the axes for new plot'''
        self._update_span()
        for key in self.axes:
            self.axes[key].clear()

    def _update_span(self):
        '''
        Updates vertical spans. Creates two arrays for the x values of Polygon.xy using the mask. 
        Note, there are 5 values in Polygon.xy as the rectangle has to be closed i.e. xy[0] =x xy[4]. Ylimits to 0 and 1 will span the whole vertical space.
        The datetime objects (new_limits) have to be converted to matplotlib numbers, which uses a different reference than Unix time -> 2001/01/01
        '''
        xmin_mask = np.array([1,1,0,0,1])
        xmax_mask = np.array([0,0,1,1,0])
        xlim_B1 = xmin_mask*mdates.date2num(self.new_limits_B1[0]) + xmax_mask*mdates.date2num(self.new_limits_B1[1])
        xlim_B2 = xmin_mask*mdates.date2num(self.new_limits_B2[0]) + xmax_mask*mdates.date2num(self.new_limits_B2[1])
        ylim = np.array([0,1,1,0,0])
        for key in ['top_left', 'middle_left', 'bottom_left']:
            self.all_poly[key].poly.xy = zip(xlim_B1, ylim)
        for key in ['top_right', 'middle_right', 'bottom_right']:
            self.all_poly[key].poly.xy = zip(xlim_B2, ylim)

    def _get_span_limits(self):
        self.new_limits_B1 = [mdates.num2date(min(self.all_poly['top_left'].poly.xy[:,0])), mdates.num2date(max(self.all_poly['top_left'].poly.xy[:,0]))]
        self.new_limits_B2 = [mdates.num2date(min(self.all_poly['top_right'].poly.xy[:,0])), mdates.num2date(max(self.all_poly['top_right'].poly.xy[:,0]))]

    def _make_plot(self):
        '''
        Plot the dataframes for xing angles, circuit currents, and orbits using the given platteau timestamps.
        The time ranged used is larger than the actual guessed platteau to get a better plot.
        '''
        xing_keys = [key for key in self.orbit_df.columns if 'XING' in key]
        xing_keys_B1 = [key for key in xing_keys if 'B1' in key]
        xing_keys_B2 = [key for key in xing_keys if 'B2' in key]
        self.axes['top_left'].set_title('Beam 1')
        self.axes['top_right'].set_title('Beam 2')
        
        self.currents_df.loc[self.time_knob:self.time_max].plot(ax=self.axes['top_left'], marker='o', ms=3, legend=False)
        self.currents_df.loc[self.time_knob:self.time_max].plot(ax=self.axes['top_right'], marker='o', ms=3, legend=False)
        self.orbit_df[xing_keys_B1].loc[self.time_knob:self.time_max].plot(ax=self.axes['middle_left'])
        self.orbit_df[xing_keys_B2].loc[self.time_knob:self.time_max].plot(ax=self.axes['middle_right'])
        self.orbit_df[['HRMS_ARC_ORBIT_B1','VRMS_ARC_ORBIT_B1']].loc[self.time_knob:self.time_max].plot(ax=self.axes['bottom_left'])
        self.orbit_df[['HRMS_ARC_ORBIT_B2','VRMS_ARC_ORBIT_B2']].loc[self.time_knob:self.time_max].plot(ax=self.axes['bottom_right'])
        self.fig.canvas.draw()

    def _normalize_data(self, df):
        '''Removes first value bias, and normalizes by range of values'''
        df = df-df.iloc[0]
        df = df/(df.max()-df.min())
        return df


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_dir", help="Specify input directory.",
        dest='input_dir',type=str,
    )
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_args()
    input_dir = args.input_dir
    print('Call interactive class.')    
    currents_filename  = os.path.join(input_dir,'data.Imeas.csv')
    platteaus_filename = os.path.join(input_dir,'data.platteaus.csv')
    orbit_filename     = os.path.join(input_dir,'data.orbit.arc.xing.csv')
    filenames = [currents_filename, orbit_filename, platteaus_filename]
    output_platteau_file = os.path.join(input_dir,'accepted_platteaus.dat')
    
    IteratePlatteauPlots(filenames, output_platteau_file)
    
