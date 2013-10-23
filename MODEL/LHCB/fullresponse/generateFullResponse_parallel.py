"""
.. module: MODEL.LHCB.fullresponse.generateFullResponse_parallel

Created on ??

Creates the fullresponse and stores it in the following 'pickled' files:
 - FullResponse
 - FullResponse_couple
 - FullResponse_chromcouple
 The files are saved in option -p. They are used in the correction scripts.

Options::

  -a ACCEL, --accel=ACCEL
                        Which accelerator: LHCB1 LHCB2 SPS RHIC SOLEIL
  -p PATH, --path=PATH  path to save. Have to contain 'job.iterate.madx' and 'modifiers.madx'
  -c CORE, --core=CORE  core files
  -k K, --deltak=K      delta k to be applied to quads for sensitivity matrix


.. moduleauthor:: Unknown
"""


import os
import math
import time
import cPickle
import optparse
import multiprocessing

import numpy

import __init__ # @UnusedImport init will include paths
import Python_Classes4MAD.metaclass as metaclass
import Python_Classes4MAD.madxrunner as madxrunner
import Utilities.iotools
import Utilities.math


#===================================================================================================
# parse_args()-function
#===================================================================================================
def parse_args():
    ''' Parses the arguments, checks for valid input and returns tupel '''
    parser = optparse.OptionParser()
    parser.add_option("-a", "--accel",
                      help="Which accelerator: LHCB1 LHCB2 SPS RHIC SOLEIL",
                      default="LHCB1", dest="accel")
    parser.add_option("-p", "--path",
                      help="path to save",
                      default="./", dest="path")
    parser.add_option("-c", "--core",
                      help="core files",
                      default="/afs/cern.ch/eng/sl/lintrack/Beta-Beat.src/MODEL/LHCB/fullresponse/", dest="core")
    parser.add_option("-k", "--deltak",
                      help="delta k to be applied to quads for sensitivity matrix",
                      default="0.00002", dest="k")
    
    
    (options, args) = parser.parse_args() # @UnusedVariable no args needed
    
    return options


class _InputData(object):
    """ Static class to access user input parameter and num_of_cpus and process pool"""
    output_path = ""
    delta_k = 0.0
    core_path_with_accel = ""
    
    number_of_cpus = 0
    process_pool = None

    @staticmethod
    def static_init(accel, output_path, path_to_core_files_without_accel, delta_k):
        if accel not in ("LHCB1", "LHCB2", "SPS", "RHIC", "SOLEIL"):
            raise ValueError("Unknown accelerator: "+accel)
        if not Utilities.iotools.dirs_exist(output_path):
            raise ValueError("Output path does not exists. It has to contain job.iterator.madx and modifiers.madx.")
        if not Utilities.math.can_str_be_parsed_to_number(delta_k):
            raise ValueError("Delta k is not a number: "+delta_k)
        if not Utilities.iotools.dirs_exist(os.path.join(path_to_core_files_without_accel, accel)):
            raise ValueError("Core path does not exist: "+_InputData.core_path_with_accel)
        
        _InputData.output_path = output_path
        _InputData.delta_k = float(delta_k)
        _InputData.core_path_with_accel = os.path.join(path_to_core_files_without_accel, accel)
        _InputData.number_of_cpus = multiprocessing.cpu_count()
        _InputData.process_pool = multiprocessing.Pool(processes=_InputData.number_of_cpus)

    def __init__(self):
        raise NotImplementedError("static class _InputData cannot be instantiated")


#=======================================================================================================================
# main()-function
#=======================================================================================================================
def main(accel, output_path, path_to_core_files_without_accel, delta_k):
    
    _InputData.static_init(accel, output_path, path_to_core_files_without_accel, delta_k)
    
    _generate_fullresponse_for_chromatic_coupling()
    _generate_fullresponse_for_coupling()
    _generate_fullresponse_for_beta()
    

def _generate_fullresponse_for_chromatic_coupling():
    variables = None
    FullResponse = {}   #Initialize FullResponse
    execfile(os.path.join(_InputData.core_path_with_accel, "AllLists_chromcouple.py"))
    exec('variables=kss()')           #Define variables
    delta1 = numpy.zeros(len(variables)) * 1.0   #Zero^th of the variables
    incr = numpy.ones(len(variables)) * 0.05    #increment of variables
    dpp = 0.0001
    FullResponse['incr'] = incr           #Store this info for future use
    FullResponse['delta1'] = delta1
    
    
    ######## loop over normal variables
    f = open(_join_with_output("iter.madx"), "w")
    for i in range(0, len(delta1)) : #Loop over variables
        delta = numpy.array(delta1)
        delta[i] = delta[i] + incr[i]
        var = variables[i]
        print >> f, var, "=", var, "+(", delta[i], ");"
        print >> f, "twiss, deltap= " + str(dpp) + ",file=\"" + _join_with_output("twiss.dp+.") + var + "\";"
        print >> f, "twiss, deltap=-" + str(dpp) + ",file=\"" + _join_with_output("twiss.dp-.") + var + "\";"
        print >> f, var, "=", var, "-(", delta[i], ");"
    
    
    print >> f, "twiss, deltap= " + str(dpp) + ",file=\"" + _join_with_output("twiss.dp+.0")+"\";"
    print >> f, "twiss, deltap=-" + str(dpp) + ",file=\"" + _join_with_output("twiss.dp-.0")+"\";"
    f.close()
    print "Running MADX"
    _parallel_command(period=4, number_of_cases=len(delta1) + 1) # period=4 since there are 4 lines in iter.madx per case, number_of_cases has +1 since there is the 0 case
    
    
    
    varsforloop = variables + ['0']
    newvarsforloop = []
    for value in varsforloop:
        newvarsforloop.append([value, _InputData.output_path, dpp])
    a = _InputData.process_pool.map(_loadtwiss_chrom_coup, newvarsforloop)
    for key, value in a:
        FullResponse[key] = value
    
    _dump(_join_with_output('FullResponse_chromcouple'), FullResponse)
    
    
def _generate_fullresponse_for_coupling():
    variables = None
    FullResponse = {}   #Initialize FullResponse
    execfile(os.path.join(_InputData.core_path_with_accel, "AllLists_couple.py"))
    exec('variables=Qs()')           #Define variables
    delta1 = numpy.zeros(len(variables)) * 1.0   #Zero^th of the variables
    incr = numpy.ones(len(variables)) * 0.0001    #increment of variables
    
    
    FullResponse['incr'] = incr           #Store this info for future use
    FullResponse['delta1'] = delta1       #"     "     "
    
    ######## loop over normal variables
    f = open(_join_with_output('iter.madx'), 'w')
    for i in range(0, len(delta1)) : #Loop over variables
        delta = numpy.array(delta1)
        delta[i] = delta[i] + incr[i]
        var = variables[i]
        print >> f, var, "=", var, "+(", delta[i], ");"
        print >> f, "twiss, file=\"" + _join_with_output("twiss." + var)+"\";"
        print >> f, var, "=", var, "-(", delta[i], ");"
    
    print >> f, "twiss, file=\"" + _join_with_output("twiss.0")+"\";"
    f.close()
    #Sending the mad jobs in parallel
    _parallel_command(period=3, number_of_cases=len(delta1) + 1)
    
    #Loading the twiss files into fullresp in parallel
    varsforloop = variables + ['0']
    newvarsforloop = []
    for value in varsforloop:
        newvarsforloop.append([value, _InputData.output_path])
    a = _InputData.process_pool.map(_loadtwiss_coup, newvarsforloop)
    for key, value in a:
        FullResponse[key] = value
        
    _dump(_join_with_output("FullResponse_couple"), FullResponse)
    
    
def _generate_fullresponse_for_beta():
    variables = None
    FullResponse = {}   #Initialize FullResponse
    execfile(os.path.join(_InputData.core_path_with_accel, "AllLists.py"))
    exec('variables=Q()')           #Define variables
    delta1 = numpy.zeros(len(variables)) * 1.0   #Zero^th of the variables
    #incr=ones(len(variables))*0.00005    #increment of variables    #### when squeeze low twiss fails because of to big delta
    incr = numpy.ones(len(variables)) * _InputData.delta_k
    
    
    FullResponse['incr'] = incr           #Store this info for future use
    FullResponse['delta1'] = delta1       #"     "     "
    
    ######## loop over normal variables
    f = open(_join_with_output("iter.madx"), "w")
    for i in range(0, len(delta1)) : #Loop over variables
        delta = numpy.array(delta1)
        delta[i] = delta[i] + incr[i]
        var = variables[i]
        print >> f, var, "=", var, "+(", delta[i], ");"
        print >> f, "twiss, file=\"" + _join_with_output("twiss." + var) + "\";"
        print >> f, var, "=", var, "-(", delta[i], ");"
    
    print >> f, "twiss,file=\"" + _join_with_output("twiss.0")+"\";"
    f.close()
    
    _parallel_command(period=3, number_of_cases=len(delta1) + 1)
    
    #Loading the twiss files into fullresp in parallel
    varsforloop = variables + ['0']
    newvarsforloop = []
    for value in varsforloop:
        newvarsforloop.append([value, _InputData.output_path])
    a = _InputData.process_pool.map(_loadtwiss_beta, newvarsforloop)
    for key, value in a:
        FullResponse[key] = value
    
    _dump(_join_with_output("FullResponse"), FullResponse)
    
    
#=======================================================================================================================
# helper functions
#=======================================================================================================================

def _join_with_output(*path_tokens):
    return os.path.join(_InputData.output_path, *path_tokens)


DEV_NULL = open(os.devnull, "w")

def _callMadx(pathToInputFile, attemptsLeft=5):
    result = madxrunner.runForInputFile(pathToInputFile, stdout=DEV_NULL)
    if result is not 0: # then madx failed for whatever reasons, lets try it again (tbach)
        print "madx failed. result:", result, "pathToInputFile:", pathToInputFile, "attempts left:", attemptsLeft
        if attemptsLeft is 0:
            raise Exception("madx finally failed, can not continue")
        print "lets wait 0.5s and try again..."
        time.sleep(0.5)
        return _callMadx(pathToInputFile, attemptsLeft - 1)
    return result
    
def _dump(pathToDump, content):
    dumpFile = open(pathToDump, 'wb')
    cPickle.Pickler(dumpFile, -1).dump(content)
    dumpFile.close()


def _parallel_command(period, number_of_cases):
    iterfile=open(_join_with_output("iter.madx"), 'r')
    lines=iterfile.readlines()
    iterfile.close()
    casesperprocess=int(math.ceil(number_of_cases*1.0/_InputData.number_of_cpus))
    linesperprocess=casesperprocess*period
    
    iterFilePaths = []
    for i in range(len(lines)):      #split the iter.madx using in final number of processes 
        if (i % linesperprocess == 0):
            proid = i / linesperprocess + 1
            iterFilePath = _join_with_output("iter." + str(proid) + ".madx")
            iterFile = open(iterFilePath, 'w')
            iterFilePaths.append(iterFilePath)
        iterFile.write(lines[i])
        if i == len(lines) - 1 or (i % linesperprocess == linesperprocess - 1):
            iterFile.close()
            
    
    # Prepare copies of the job.iterate.madx and all the shell commands
    madxFilePaths = []
    for i in range(1,proid+1):
        cmd='sed \'s/iter.madx/iter.'+str(i)+'.madx/g\' '+_InputData.output_path+'/job.iterate.madx > '+_InputData.output_path+'/job.iterate.'+str(i)+'.madx'
        _shell_command(cmd)
        madxFilePaths.append(_InputData.output_path+'/job.iterate.'+str(i)+'.madx')
    
#    print "send jobs to madx in parallel, number of jobs:", len(madxFilePaths)
    _InputData.process_pool.map(_callMadx, madxFilePaths)
    
    # clean up again (tbach)
    for madxFilePathsItem in madxFilePaths:
        os.remove(madxFilePathsItem)
    for iterFilePathsItem in iterFilePaths:
        os.remove(iterFilePathsItem)


def _shell_command(cmd):
#    print 'process id:', os.getpid()
    ret = os.system(cmd)
    if ret is not 0:
        raise ValueError("COMMAND: %s finished with exit value %i" % (cmd, ret))


def _loadtwiss_beta(varandpath):
    (var, path) = varandpath
#    print "Reading twiss." + var
    x = 0
    try:
        x = metaclass.twiss(path + "/twiss." + var)
        os.remove(path + "/twiss." + var)
    except IOError as e:
        print e
        return []
    return var, x

def _loadtwiss_coup(varandpath):
    var, path = varandpath
#    print "Reading twiss." + var
    x = 0
    try:
        x = metaclass.twiss(path + "/twiss." + var)
        x.Cmatrix()
        os.remove(path + "/twiss." + var)
    except IOError as e:
        print e
        return []
    return var, x

def _loadtwiss_chrom_coup(varandpathanddpp):
    var, path, dpp = varandpathanddpp
#    print  "Reading twiss.dp+." + var
    xp = 0
    xm = 0
    try:
        xp = metaclass.twiss(path + "/twiss.dp+." + var)
        xp.Cmatrix()
#    print  "Reading twiss.dp-." + var
        xm = metaclass.twiss(path + "/twiss.dp-." + var)
        xm.Cmatrix()
    except IOError as e:
        print e
        return []
    # Initializing and Calculating chromatic coupling for every BPM
    xp.Cf1001r = []
    xp.Cf1001i = []
    xp.Cf1010r = []
    xp.Cf1010i = []
    for j in range(len(xp.NAME)):

        vvv = (xp.F1001R[j] - xm.F1001R[j]) / (2 * dpp)
        xp.Cf1001r.append(vvv)

        vvv = (xp.F1001I[j] - xm.F1001I[j]) / (2 * dpp)
        xp.Cf1001i.append(vvv)

        vvv = (xp.F1001R[j] - xm.F1001R[j]) / (2 * dpp)
        xp.Cf1010r.append(vvv)

        vvv = (xp.F1010I[j] - xm.F1010I[j]) / (2 * dpp)
        xp.Cf1010i.append(vvv)

    os.remove(path + "/twiss.dp+." + var)
    os.remove(path + "/twiss.dp-." + var)
    return var, xp



#=======================================================================================================================
# main invocation
#=======================================================================================================================
def _start():
    timeStartGlobal = time.time()
    options = parse_args()
    
    main(
         accel=options.accel, 
         output_path=options.path, 
         path_to_core_files_without_accel=options.core, 
         delta_k=options.k
         )
    
    timeGlobal = time.time() - timeStartGlobal
    print "Duration:", timeGlobal, "s"

if __name__ == '__main__':
    _start()
    
