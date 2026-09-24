#!/usr/bin/python
'''
This source code is distributed under the MIT License

Copyright (c) 2010, Jens Neuhalfen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''

import kpage
import physmem
import status
import scheduling
import sys
import tester
import frame
from tester.scanner_baseclass import ScannerBaseclass
# //LZU CHANGE
from injection_state import DEFAULT_INJECTION_STATE_PATH

import os
import re
import time
from optparse import OptionParser


def parse_memory_size(value):
    """Convert values such as 512M, 2G or 4GiB to bytes."""
    match = re.match(r"^([1-9][0-9]*)\s*([KMGT]?)(?:I?B)?$", value.strip(), re.I)
    if not match:
        raise ValueError("use a size such as 512M, 2G or 4GiB")

    amount = int(match.group(1))
    unit = match.group(2).upper()
    shifts = {"": 0, "K": 10, "M": 20, "G": 30, "T": 40}
    return amount << shifts[unit]


def select_local_pfn_range(max_memory_bytes, num_frames,
                           iomem_path="/proc/iomem"):
    """Select the largest page-aligned System RAM range for a local scan."""
    page_size = physmem.PAGE_SIZE
    ranges = []

    with open(iomem_path, "r") as iomem:
        for line in iomem:
            address_range, separator, description = line.partition(":")
            if not separator or description.strip() != "System RAM":
                continue

            start_text, separator, end_text = address_range.strip().partition("-")
            if not separator:
                continue

            try:
                start_address = int(start_text, 16)
                end_address = int(end_text, 16)
            except ValueError:
                continue

            if end_address < start_address:
                continue

            first_pfn = (start_address + page_size - 1) // page_size
            last_pfn = (end_address + 1) // page_size
            last_pfn = min(last_pfn, int(num_frames))
            if last_pfn > first_pfn:
                ranges.append((first_pfn, last_pfn))

    if not ranges:
        raise RuntimeError(
            "no usable System RAM range was found in %s; "
            "check whether /proc/iomem exposes physical addresses" % iomem_path
        )

    first_pfn, system_ram_last_pfn = max(
        ranges, key=lambda item: item[1] - item[0]
    )
    max_pages = max_memory_bytes // page_size
    if max_pages < 1:
        raise ValueError("max-memory must cover at least one memory page")

    last_pfn = min(system_ram_last_pfn, first_pfn + max_pages)
    return first_pfn, last_pfn, system_ram_last_pfn

serial_available = True
try:
    import serial
except ImportError:
    serial_available = False

class PrintTestReporting:
    def report_bad_memory(self, bad_offset, expected_value, actual_value):
        print("BAD memory, offset 0x%x : Expected/Got 0x%x/0x%x" % (bad_offset, expected_value, actual_value))

class PrintSchedulerReporting:
    def __init__(self, chunksize, logfile, serdev):
        self.chunksize = chunksize
        self.enabled = (chunksize != 0)
        self.logfile = logfile
        self.serdev  = serdev
        self.reset()

    def reset(self):
        self.frames_tested  = 0
        self.frames_tested_c  = 0
        self.start_of_measurement = time.time()
        self.start_of_chunk = self.start_of_measurement
        self.tested_frames = []
        if (self.logfile != None):
            with open(self.logfile, 'a') as fd:
                fd.write("---log reset---\n")

    def report_good_frame(self, pfn):

        self.report_frame_tested(pfn)

    # LZU DSLAB CHANGE

    '''
    def report_bad_frame(self, pfn):
        self.serdev.write("bad frame at pfn %08x\n" % pfn)
        self.report_frame_tested(pfn)
        '''
    def report_bad_frame(self, pfn):
        if self.serdev:
            self.serdev.write("bad frame at pfn %08x\n" % pfn)
        else:
            print("[WARNING] bad frame at pfn %08x (no serdev)" % pfn)
        self.report_frame_tested(pfn)

    def report_frame_tested(self, pfn):
        self.frames_tested += 1
        self.frames_tested_c += 1
        self.tested_frames.append(pfn)
        if self.enabled:
            if (self.frames_tested % self.chunksize) == 0:
                self.print_stats()

    def print_stats(self):
        seconds_since_start = time.time() - self.start_of_measurement
        seconds_since_start_c = time.time() - self.start_of_chunk

        if (seconds_since_start_c > 0):
            fps = self.frames_tested / seconds_since_start
            fps_c = self.frames_tested_c / seconds_since_start_c

            if (self.logfile != None):
                with open(self.logfile, 'a') as fd:
                    fd.write("pass: %d frames %d seconds (%d fps) - chunk: %d frames %d seconds (%d fps)\n" % (self.frames_tested,
                                                                                                               seconds_since_start,
                                                                                                               fps,
                                                                                                               self.frames_tested_c,
                                                                                                               seconds_since_start_c,
                                                                                                               fps_c))

            print("Tested %d frames in %ds. fps=%d (this batch: %d in %d s: fps=%d)" % (self.frames_tested,seconds_since_start, fps, self.frames_tested_c, seconds_since_start_c,fps_c))
            self.frames_tested_c = 0
            self.start_of_chunk = time.time()

        if self.serdev and len(self.tested_frames) > 0:
            self.tested_frames.sort()

            range_start = None
            prev_pfn    = -2

            self.serdev.write("tested")

            for pfn in self.tested_frames:
                if pfn != prev_pfn + 1:

                    if range_start != None:
                        self.serdev.write(" %08x-%08x" % (range_start, prev_pfn))

                    range_start = pfn

                prev_pfn = pfn

            if range_start != None:

                self.serdev.write(" %08x-%08x" % (range_start, prev_pfn))

            self.serdev.write("\n");

        self.tested_frames = []

def print_stats(config, timestamping, pageflags, logfile, serdev,
                first_frame=0, last_frame=None):

    num_tested = 0
    num_untested = 0
    num_untestable = 0

    total_claim_time  = 0
    min_claim_time = None
    max_claim_time = 0

    total_last_test_timestamp = 0
    min_last_test_timestamp = None
    max_last_test_timestamp = 0

    num_errors = 0
    total_frames = int(config.get_record_count())
    first_frame = int(first_frame)
    if last_frame is None:
        last_frame = total_frames
    last_frame = min(int(last_frame), total_frames)
    num_frames = last_frame - first_frame
    num_nopage = 0
    num_recent = 0

    retest_limit = timestamping.timestamp() - timestamping.seconds_to_timestamp(options.retest_time)

    if serdev:
        serdev.write("calculating stats\n")

    # LZU DSLAB CHANGE

    print(
        "开始统计 PFN %d - %d，共 %d 个页面，请等待……" % (
            first_frame,
            last_frame - 1,
            num_frames,
        ),
        flush=True,
    )

    for pfn in range(first_frame, last_frame):
        processed = pfn - first_frame
        if processed > 0 and processed % 1000000 == 0:
            print(
                "统计进度：%d / %d PFN（%.1f%%）" % (
                    processed,
                    num_frames,
                    100.0 * processed / num_frames,
                ),
                flush=True,
            )

        frame = config[pfn]

        is_tested = (frame.last_successful_test > 0) or (frame.last_failed_test > 0)

        if is_tested:
            num_tested += 1
            # LZU DSLAB CHANGE

            if (min_last_test_timestamp is None or frame.last_successful_test < min_last_test_timestamp) and frame.last_successful_test > 0:
                min_last_test_timestamp = frame.last_successful_test

            if (frame.last_successful_test > max_last_test_timestamp) or (0 == max_last_test_timestamp):
                max_last_test_timestamp = frame.last_successful_test

            # LZU DSLAB CHANGE   

            if (min_last_test_timestamp is None or frame.last_failed_test < min_last_test_timestamp) and frame.last_failed_test > 0:
                min_last_test_timestamp = frame.last_failed_test

            if (frame.last_failed_test > max_last_test_timestamp) or (0 == max_last_test_timestamp):
                max_last_test_timestamp = frame.last_failed_test

            total_last_test_timestamp += frame.last_successful_test

            # LZU DSLAB CHANGE

            if (min_claim_time is None or frame.last_claiming_time_jiffies < min_claim_time):
                min_claim_time = frame.last_claiming_time_jiffies

            if (frame.last_claiming_time_jiffies > max_claim_time) or (0 == max_claim_time):
                max_claim_time = frame.last_claiming_time_jiffies

            total_claim_time +=  frame.last_claiming_time_jiffies

            if (frame.num_errors > 0 ):
                num_errors += 1

            last_test = 0
            if frame.last_successful_test > 0:
                last_test = frame.last_successful_test

            if frame.last_failed_test > last_test:
                last_test = frame.last_failed_test

            if last_test > retest_limit:
                num_recent += 1

        else:

            if (pageflags[pfn].any_set_in(1 << 32)):
                num_untestable += 1
            elif not (pageflags[pfn].any_set_in(1 << 20)): # don't count pages that do not exist
                num_untested += 1
            else:
                num_nopage += 1

    num_testable_frames = num_tested + num_untested

    # LZU DSLAB CHANGE
    message =  "%d (0x%x) testable frames, %d (0x%x) total frames:\n" % (int(num_testable_frames), int(num_testable_frames), int(num_frames), int(num_frames))
    message += "%8d tested          (%5.1f%%)\n" % (int(num_tested), (100.0 * num_tested/num_testable_frames))
    message += "%8d recently tested (%5.1f%%)\n" % (int(num_recent), (100.0 * num_recent / num_testable_frames))
    message += "%8d untested        (%5.1f%%)\n" % (int(num_untested), (100.0 * num_untested/num_testable_frames))
    message += "%8d untestable"                  % int(num_untestable)
    message += "%8d nopage"                      % int(num_nopage)
    message += "%8d have seen errors\n"          % int(num_errors)

    if (logfile != None):
        with open(logfile, 'a') as fd:
            fd.write("==== stats at %d ====\n" % time.time())
            fd.write(message)
            fd.write("^^^^ stats ^^^^\n")

    # LZU DSLAB CHANGE
    print("\n" + message, flush=True)
    if num_tested > 0:
        print("\nFor tested frames, the following statistics have been calculated: ")
        print("   Time it took to claim a frame (in jiffies) (min,max,avg) : %d, %d, %d" % (min_claim_time, max_claim_time, total_claim_time / num_tested))
        print("   Timestamp of last test (min,max,avg) : %s, %s, %s\n" % (timestamping.to_string( min_last_test_timestamp, '-'), timestamping.to_string(max_last_test_timestamp), timestamping.to_string(total_last_test_timestamp / num_tested)))

    if serdev:
        serdev.write("starting test pass\n")

    return num_tested

def reset_first_10_frames_in_config(path):
    """
    Reset the first 10 frames of the config
    """
    num_frames = 10
    cfg = status.FileBasedConfiguration(path, num_frames,  frame.FrameStatus)
    with cfg.open() as s:
        # LZU DSLAB CHANGE

        for idx in range(0,int(num_frames)):
            stat = s[idx]
            stat.last_successful_test = 0
            stat.last_failed_test = idx

    with cfg.open() as s:
        # LZU DSLAB CHANGE

        for idx in range(0,int(num_frames)):
            stat = s[idx]
            if  (stat.last_successful_test != 0) or ( stat.last_failed_test != idx):
                print("Error @%d: got %s" % (idx,stat))

if __name__ == '__main__':

    usage = """This tool tests your computers memory. Be sure that the phys_mem module is loaded! Also, access to  `/proc/kpageflags`/`/proc/kpagecount` is needed
    usage: %prog [options]"""
    parser = OptionParser(usage=usage)

    parser.add_option("-a", "--allocation-strategy",dest="strategy",type="choice",
                      default="slow",choices=["blockwise","frame-by-frame","slow"],
                      help="Algorithm used to allocate memory: `blockwise`, `slow` and `frame-by-frame`."
                           "[default: %default]")

    shortnames = ""
    for cls in ScannerBaseclass.scanner_classes:
        shortnames = shortnames + (("`%s`, ") % (cls.shortname()))
    parser.add_option("-t", "--test-algorithms",dest="algorithms_str",action="store", default="linear-cext",
                      help="Algorithms used to test memory: "+shortnames[0:-2]+" and `?` for more detailed information about algorithms. "
                     "[default: %default]")

    parser.add_option("-f", "--report-frequency",dest="report_every",
                      default=50,type=int ,
                      help="Report performance statistics every REPORT_EVERY frames. `0` disables this report."
                           "[default: %default]")

    parser.add_option("-s", "--status_file",dest="status_file",
                      default='/tmp/memtest_status',
                      metavar="PATH", help="The path to the status file used by this program. The file will be created, if it does not exists. [default: %default]")

    parser.add_option("-r", "--run-time",dest="run_time",
                      default=5*60,type=int,
                      help="(slow scheduler only) Time for a single full test of all frames (no hotplug/shake)")
    # LZU DSLAB CHANGE
    '''
    parser.add_option("-d", "--disruptive-time",dest="disruptive_time",
                      default=1*60,type=int,
                      help="(slow scheduler only) Maximum time to spend in disruptive tests (hotplug/shaking)")

    parser.add_option("-e", "--exact-disruptive",dest="exact_disruptive",action="store_true",
                      default=False,
                      help="(slow scheduler only) Sleep if disruptive tests need less time than --disruptive-time")
    '''
    parser.add_option("--frames-per-check",dest="frames_per_check",
                      default=16384/4,type=int,
                      help="(slow scheduler only) number of frames to check between sleeps")

    parser.add_option("-1",dest="run_pass1",action="store_true",default=False,
                      help="run pass 1 (buddy-claimer)")
    # LZU DSLAB CHANGE
    '''
    parser.add_option("-2",dest="run_pass2",action="store_true",default=False,
                      help="run pass 2 (hotplug+buddy-claimer)")

    parser.add_option("-3",dest="run_pass3",action="store_true",default=False,
                      help="run pass 3 (shaking+hotplug+buddy-claimer)")
    '''

    parser.add_option("--memtester-args",
                  dest="memtester_args",
                  default="",
                  help="extra arguments to pass to memtester")

    parser.add_option("--memtester-inject-type", "--memtester-inject-kind",
                  dest="memtester_inject_type",
                  default=None,
                  type="int",
                  metavar="TYPE",
                  help="memtester error injection type passed as -c TYPE: "
                       "0=none, 1=Stuck Address, 2=Compare XOR, 3=Solid Bits, "
                       "4=Checkerboard, 5=Walking Zeroes, 6=Compare OR, "
                       "7=8-bit Writes")

    # //LZU CHANGE
    parser.add_option("--memtester-inject-file",
                  dest="memtester_inject_file",
                  default=DEFAULT_INJECTION_STATE_PATH,
                  metavar="PATH",
                  help="shared file changed by injection_control.py "
                       "[default: %default]")

    parser.add_option("-4",dest="run_pass4",action="store_true",default=False,
                      help="run pass 4 (custom claimers, see --enable-p4-claimers)")

    parser.add_option("--enable-p4-claimers",dest="pass4_claim_str", action="store",default="",
                      help="select claimers to run in pass 4")

    parser.add_option("--no-delay", dest="no_delay", action="store_true", default = False,
                      help="Do not sleep while idle")

    parser.add_option("--retest-time", dest="retest_time", default=24*60*60, type=int,
                      help="time between repeated tests of a frame in seconds")

    parser.add_option("--logfile", dest="report_logfile", default=None,
                      help="frame test statistics log file")

    parser.add_option("--scan-mode", dest="scan_mode", type="choice",
                      choices=["full", "local"], default="full",
                      help="scan the whole machine or a bounded local System RAM "
                           "range: `full` or `local` [default: %default]")

    parser.add_option("--max-memory", dest="max_memory", default=None,
                      metavar="SIZE",
                      help="entire System RAM range processed in local mode, "
                           "for example 512M, 2G or 4GiB")

    if serial_available:
        parser.add_option("--serial", dest="serial_port", default=None,
                          help="device for serial status output")

    (options, args) = parser.parse_args()

    if len(args) != 0:
        parser.error("No arguments supported!")

    if options.report_every < 0:
        parser.error("report-frequency must be > 0")

    if (options.memtester_inject_type is not None and
            not 0 <= options.memtester_inject_type <= 7):
        parser.error("memtester-inject-type must be between 0 and 7")

    if options.scan_mode == "local":
        if options.max_memory is None:
            parser.error("--scan-mode=local requires --max-memory=SIZE")
        try:
            local_max_memory = parse_memory_size(options.max_memory)
        except ValueError as error:
            parser.error("invalid --max-memory: %s" % error)

        # Local mode is one bounded demonstration run. Keep its status
        # separate from a full scan and retry pages immediately.
        options.strategy = "slow"
        options.status_file = "/tmp/rampage_memtest_status_local"
        options.retest_time = 0
        options.no_delay = True
        if options.report_logfile is None:
            options.report_logfile = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "rampage-local.log",
            )
    else:
        if options.max_memory is not None:
            parser.error("--max-memory is only valid with --scan-mode=local")
        local_max_memory = None

    path = options.status_file

    all_passes = False
    # LZU DSLAB CHANGE
    '''
    if not options.run_pass1 and not options.run_pass2 and not options.run_pass3 and not options.run_pass4:
        all_passes = True
        options.run_pass1 = True
        options.run_pass2 = True
        options.run_pass3 = True
    '''
    if not options.run_pass1 and not options.run_pass4:
        all_passes = True
        options.run_pass1 = True

    if options.run_pass4 and options.pass4_claim_str == "":
        parser.error("No claimers selected for pass 4")

    pass4_claimers = 0

    if len(options.pass4_claim_str) > 0:
        for word in options.pass4_claim_str.split(","):
            if word in physmem.claimer_names:
                pass4_claimers = pass4_claimers | physmem.claimer_names[word]
            else:
                print("ERROR: Unknown claimer name >%s<" % word)
                print("Available claimers:")
                for claimer in physmem.claimer_names.keys():
                    # LZU DSLAB CHANGE

                    print("  %s")  % claimer
                exit(1)

    available_algos = dict([(cls.shortname(), cls) for cls in ScannerBaseclass.scanner_classes])

    if options.algorithms_str == "?":
        # LZU DSLAB CHANGE

        print("Available test algorithms:")
        maxlen = max([len(s) for s in available_algos])
        for alg in sorted(available_algos):
            # LZU DSLAB CHANGE

            print(f"   {alg:<{maxlen}}: {available_algos[alg].name()}")
        exit(1)

    test_algos = []
    if len(options.algorithms_str) > 0:
        for word in options.algorithms_str.split(","):
            if word in available_algos:
                test_algos.append(word)
            elif word[-1] == "*":

                for alg in available_algos:
                    if word[0:-1] == alg[0:len(word)-1]:
                        test_algos.append(alg)
            else:
                print("ERROR: Unknown algorithm name >%s<" % word)
                exit(2)

    test_algos = list(set(test_algos))

    reporter = PrintTestReporting()
    # LZU DSLAB CHANGE

    # //LZU CHANGE
    device_name = "/dev/phys_mem"
    physmem_dev  = physmem.Physmem(device_name)

    test_algos = []    
    for a in options.algorithms_str.split(","):
        cls = available_algos[a]
        if cls.shortname() == "memtester":
            # //LZU CHANGE
            test_algos.append(cls(reporter, options.memtester_args,
                                   options.memtester_inject_type,
                                   options.memtester_inject_file,
                                   physmem_dev))
        else:
            test_algos.append(cls(reporter))

    timestamping = status.TimestampingFacility()

    pageflags = kpage.FlagsDataSource('flags', "/proc/kpageflags").open()
    pagecount = kpage.CountDataSource('count', "/proc/kpagecount").open()

    num_frames = pageflags.num_frames()
    frame_config_class = frame.FrameStatus

    if options.scan_mode == "local":
        try:
            local_first_frame, local_last_frame, system_ram_last_frame = (
                select_local_pfn_range(local_max_memory, num_frames)
            )
        except (OSError, RuntimeError, ValueError) as error:
            parser.error("cannot select local scan range: %s" % error)

        local_bytes = (local_last_frame - local_first_frame) * physmem.PAGE_SIZE
        print("局部测试模式：在指定范围内执行完整测试流程", flush=True)
        print(
            "自动选择 System RAM：PFN %d - %d" % (
                local_first_frame,
                system_ram_last_frame - 1,
            ),
            flush=True,
        )
        print(
            "本次完整处理范围：PFN %d - %d，共 %.2f MiB（上限 %s）" % (
                local_first_frame,
                local_last_frame - 1,
                local_bytes / float(1024 * 1024),
                options.max_memory,
            ),
            flush=True,
        )
        print("完成整个指定范围后自动退出", flush=True)

    cfg = status.FileBasedConfiguration(path, num_frames, frame_config_class)

    if serial_available and options.serial_port != None:
        # LZU DSLAB CHANGE

        print("Using serial port %s for status" % options.serial_port)
        serdev = serial.Serial(options.serial_port, 115200)
    else:
        serdev = None

    reporting = PrintSchedulerReporting(options.report_every, options.report_logfile, serdev)

    if  "frame-by-frame" == options.strategy:
        scheduler_factory = scheduling.simple.SimpleSchedulerFactory(physmem_dev, test_algos,  pageflags, pagecount, reporting, options.retest_time)
    elif "blockwise" == options.strategy:
        scheduler_factory =  scheduling.blockwise.SimpleBlockwiseSchedulerFactory(physmem_dev, test_algos, pageflags, pagecount, timestamping, reporting, options.retest_time)
    elif "slow" == options.strategy:
        scheduler_factory =  scheduling.slow.SlowSchedulerFactory(physmem_dev, test_algos, pageflags, pagecount, timestamping, reporting, options.retest_time)

    # LZU DSLAB CHANGE

    print("Using the '%s' with %d test algorithm%s" % (
    scheduler_factory.name(),
    len(test_algos),
    "" if len(test_algos) == 1 else "s"))

    if options.scan_mode == "local":
        print("------ local pass 1 (Buddy-Claimer) ------", flush=True)
        local_start_time = time.time()
        with cfg.open() as s:
            print_stats(
                s,
                timestamping,
                pageflags,
                options.report_logfile,
                serdev,
                local_first_frame,
                local_last_frame,
            )
            scheduler = scheduler_factory.new_instance(s)
            reporting.reset()
            tested = scheduler.run(
                local_first_frame,
                local_last_frame,
                physmem.SOURCE_FREE_BUDDY_PAGE,
                options.frames_per_check,
                0,
                0,
            )
            reporting.print_stats()
            print_stats(
                s,
                timestamping,
                pageflags,
                options.report_logfile,
                serdev,
                local_first_frame,
                local_last_frame,
            )

        elapsed = time.time() - local_start_time
        print(
            "局部范围测试完成：成功申请并测试 %d 个页面，用时 %.2f 秒" %
            (tested, elapsed),
            flush=True,
        )
        sys.exit(0 if tested > 0 else 1)

    looptest = 0
    previously_tested = -1
    delay_factor = 1

    while True:
        # LZU DSLAB CHANGE

        print("(loop %d)" % looptest)
        looptest = looptest + 1

        with cfg.open() as s:

            tested = print_stats(s,timestamping,pageflags,options.report_logfile,serdev)
            if not options.no_delay and previously_tested == tested:

                # LZU DSLAB CHANGE

                print("Nothing happened, sleeping for %d second%s" % (
                delay_factor, 
                "s" if delay_factor != 1 else ""
                ))
                time.sleep(delay_factor)
                delay_factor = 2*delay_factor

                if delay_factor > 500:
                    delay_factor = 500
            else:

                delay_factor = 1

            previously_tested = tested

        with cfg.open() as s:
            scheduler = scheduler_factory.new_instance(s)

            if options.run_pass1:

                # LZU DSLAB CHANGE

                print("------ pass 1 (Buddy-Claimer) ------")
                starttime = time.time()
                while time.time() - starttime < options.run_time:
                    reporting.reset()

                    max_runtime = options.run_time - (time.time() - starttime)
                    # LZU DSLAB CHANGE

                    if hasattr(scheduler, "run") and scheduler.__class__.__name__ == "SimpleScheduler":
                        scheduler.run(0, num_frames, physmem.SOURCE_FREE_BUDDY_PAGE)
                    else:
                        scheduler.run(0, num_frames, physmem.SOURCE_FREE_BUDDY_PAGE, options.frames_per_check, max_runtime, options.run_time)
                    reporting.print_stats()

            starttime = time.time()
            # LZU DSLAB CHANGE
            '''
            if options.run_pass2:

                # LZU DSLAB CHANGE

                print("------ pass 2 (Hotplug) ------")   
                reporting.reset()
                scheduler.run(0,num_frames, physmem.SOURCE_HOTPLUG_CLAIM + physmem.SOURCE_FREE_BUDDY_PAGE, options.frames_per_check, options.disruptive_time)
                reporting.print_stats()

            remaining_time = options.disruptive_time - (time.time() - starttime)
            if options.run_pass3 or (all_passes and remaining_time > 0):

                # LZU DSLAB CHANGE

                print("------ pass 3 (Hotplug+Shaking) ------")
                reporting.reset()
                scheduler.run(0,num_frames, physmem.SOURCE_HOTPLUG_CLAIM + physmem.SOURCE_SHAKING + physmem.SOURCE_FREE_BUDDY_PAGE, options.frames_per_check, remaining_time)
                reporting.print_stats()

            if (options.run_pass2 or options.run_pass3) and options.exact_disruptive:
                sleeptime = options.disruptive_time - (time.time() - starttime)
                if sleeptime > 0:
                    # LZU DSLAB CHANGE

                    print("---sleeping for %d seconds for exact disruptive_time" % sleeptime)
                    time.sleep(sleeptime)
            '''

            if options.run_pass4:

                # LZU DSLAB CHANGE

                print("------ pass 4 (%s) ------" % options.pass4_claim_str)
                starttime = time.time()
                while time.time() - starttime < options.run_time:
                    reporting.reset()
                    max_runtime = options.run_time - (time.time() - starttime)
                    scheduler.run(0, num_frames, pass4_claimers, options.frames_per_check, max_runtime, options.run_time)
                    reporting.print_stats()

                    if serdev:
                        print_stats(s,timestamping,pageflags,options.report_logfile,serdev)

    with cfg.open() as s:
            print_stats(s,timestamping,pageflags,options.report_logfile,serdev)
