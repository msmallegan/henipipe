import sys
import argparse
from . import henipipe
import logging
import getpass
import os
from . import sam2bed
from . import pyWriter

POLL_TIME = 5
LOG_PREFIX = '[HENIPIPE]: '

# Set up a basic logger
LOGGER = logging.getLogger('something')
myFormatter = logging.Formatter('%(asctime)s: %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(myFormatter)
LOGGER.addHandler(handler)
LOGGER.setLevel(logging.DEBUG)
myFormatter._fmt = "[HENIPIPE]: " + myFormatter._fmt


def run_henipipe(args=None):
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser('A wrapper for running henipipe')
    parser.add_argument('job', type=str, choices=['MAKERUNSHEET', 'ALIGN', 'NORM', 'SEACR'], help='a required string denoting segment of pipeline to run.  1) "MAKERUNSHEET" - to parse a folder of fastqs; 2) "ALIGN" - to perform alignment using bowtie and output bed files; 3) "NORM" - to normalize data to reference (spike in); 4) "SEACR" - to perform SEACR.')
    parser.add_argument('--sample_flag', '-sf', type=str, default="Sample", help='FOR MAKERUNSHEET only string to identify samples of interest in a fastq folder')
    parser.add_argument('--fastq_folder', '-fq', type=str, help='For MAKERUNSHEET only: Pathname of fastq folder (files must be organized in folders named by sample)')
    parser.add_argument('--genome_key', '-gk', type=str, default="blank", help='For MAKERUNSHEET only: abbreviation to use "installed" genomes in the runsheet (See README.md for more details')
    parser.add_argument('--filter_high', '-fh', type=int, default=None, help='For ALIGN only: upper limit of fragment size to exclude, defaults is no upper limit.  OPTIONAL')
    parser.add_argument('--filter_low', '-fl', type=int, default=None, help='For ALIGN only: lower limit of fragment size to exclude, defaults is no lower limit.  OPTIONAL')
    parser.add_argument('--output', '-o', type=str, default=".", help='For MAKERUNSHEET only: Pathname to write runsheet.csv file (folder must exist already!!), Defaults to current directory')
    parser.add_argument('--runsheet', '-r', type=str, help='tab-delim file with sample fields as defined in the script. - REQUIRED for all jobs except MAKERUNSHEET')
    parser.add_argument('--log_prefix', '-l', type=str, default='henipipe.log', help='Prefix specifying log files for henipipe output from henipipe calls. OPTIONAL')
    parser.add_argument('--select', '-s', type=str, default=None, help='To only run the selected row in the runsheet, OPTIONAL')
    parser.add_argument('--debug', '-d', action='store_true', help='To print commands (For testing flow). OPTIONAL')
    parser.add_argument('--bowtie_flags', '-b', type=str, default='--end-to-end --very-sensitive --no-mixed --no-discordant -q --phred33 -I 10 -X 700', help='For ALIGN: bowtie flags, OPTIONAL')
    parser.add_argument('--cluster', '-c', type=str, default='PBS', choices=['PBS', 'SLURM'], help='Cluster software.  OPTIONAL Currently supported: PBS and SLURM')
    parser.add_argument('--norm_method', '-n', type=str, default='coverage', choices=['coverage', 'read_count', 'spike_in'], help='For ALIGN and NORM: Normalization method, by "read_count", "coverage", or "spike_in".  If method is "spike_in", HeniPipe will align to the spike_in reference genome provided in runsheet. OPTIONAL')
    parser.add_argument('--user', '-u', type=str, default=None, help='user for submitting jobs - defaults to username.  OPTIONAL')
    parser.add_argument('--SEACR_norm', '-Sn', type=str, default='non', choices=['non', 'norm'], help='For SEACR: Normalization method; default is "non"-normalized, select "norm" to normalize using SEACR. OPTIONAL')
    parser.add_argument('--SEACR_stringency', '-Ss', type=str, default='stringent', choices=['stringent', 'relaxed'], help='FOR SEACR: Default will run as "stringent", other option is "relaxed". OPTIONAL')
    parser.add_argument('--verbose', '-v', default=False, action='store_true', help='Run with some additional ouput - not much though... OPTIONAL')
    #call = '/home/sfurla/Scripts/runHeniPipe.py MAKERUNSHEET -sf mini -fq /active/furlan_s/Data/CNR/190801_CNRNotch/fastq/mini/fastqs'

    #args = parser.parse_args(call.split(" ")[1:])
    args = parser.parse_args()

    #log
    if args.debug == False:
        LOGGER.info("Logging to %s... examine this file if samples fail." % args.log_prefix)

    #deal with user
    if args.user is None:
        args.user = getpass.getuser()

    #deal with paths
    if args.job=="MAKERUNSHEET":
        if os.path.isabs(args.fastq_folder) is False:
            if args.fastq_folder == ".":
                args.fastq_folder = os.getcwd()
            else :
                args.fastq_folder = os.path.abspath(args.fastq_folder)
        if os.path.exists(args.fastq_folder) is False:
            raise ValueError('Path: '+args.fastq_folder+' not found')
        if os.path.isabs(args.output) is False:
            if args.output == ".":
                args.output = os.getcwd()
            else :
                args.output = os.path.abspath(args.output)
        if os.path.exists(args.output) is False:
            raise ValueError('Path: '+args.output+' not found')
    if args.job != "MAKERUNSHEET":
        if os.path.exists(args.runsheet) is False:
            raise ValueError('Path: '+args.runsheet+' not found')


    if args.job=="MAKERUNSHEET":
        LOGGER.info("Parsing fastq folder - "+args.fastq_folder+" ...")
        LOGGER.info("Writing runsheet to - "+os.path.join(args.output, 'runsheet.csv')+" ...")
        henipipe.make_runsheet(folder=args.fastq_folder, output=args.output, sample_flag = args.sample_flag, genome_key = args.genome_key)
        exit()

    #parse and chech runsheet
    args.runsheet = os.path.abspath(args.runsheet)
    parsed_runsheet = list(henipipe.parse_runsheet(args.runsheet))
    henipipe.check_runsheet(args, parsed_runsheet, verbose=args.verbose)

    #deal with sample selection
    if args.select is not None:
        pare_down = [int(args.select) -1]
    else:
        pare_down = list(range(len(parsed_runsheet)))

    if args.job=="ALIGN":
        #deal with filtering
        LOGGER.info("Aligning reads...")
        Alignjob = henipipe.Align(runsheet_data = [parsed_runsheet[i] for i in pare_down], debug=args.debug, cluster=args.cluster, bowtie_flags=args.bowtie_flags, log=args.log_prefix, user=args.user, norm_method=args.norm_method, filter = [args.filter_low, args.filter_high])
        LOGGER.info("Submitting alignment jobs... Debug mode is %s" % args.debug)
        Alignjob.run_job()
        exit()

    if args.job=="NORM":
        LOGGER.info("Calculating %s", args.norm_method)
        Normjob = henipipe.Norm(runsheet_data = [parsed_runsheet[i] for i in pare_down], debug=args.debug, cluster=args.cluster, log=args.log_prefix, norm_method=args.norm_method, user=args.user)
        LOGGER.info("Submitting bedgraph jobs... Debug mode is %s" % args.debug)
        Normjob.run_job()
        exit()

    if args.job=="SEACR":
        LOGGER.info("Running SEACR using settings: SEACR_norm = %s, SEACR_stringency = %s" % (args.SEACR_norm, args.SEACR_stringency))
        SEACRjob = henipipe.SEACR(runsheet_data = parsed_runsheet, pare_down = pare_down, debug=args.debug, cluster=args.cluster, norm=args.SEACR_norm, stringency=args.SEACR_stringency, user=args.user, log=args.log_prefix)
        SEACRjob.run_job()
        exit()


if __name__ == "__main__":
    run_henipipe()
