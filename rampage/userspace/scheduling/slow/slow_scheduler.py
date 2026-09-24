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

import math
import time
import frame
import physmem

class SlowSchedulerFactory():
    def __init__(self, physmem_device,frame_tests,  kpageflags, kpagecount, timestamping, reporting, untested_age):
        '''
        Constructor
        '''
        self.kpageflags = kpageflags
        self.kpagecount = kpagecount
        self.physmem_device = physmem_device
        self.frame_tests = frame_tests
        self.timestamping = timestamping
        self.max_untested_age = untested_age

        self.reporting =  reporting

    def new_instance(self, frame_stati):
       return SlowScheduler( self.physmem_device, self.frame_tests, frame_stati, self.kpageflags, self.kpagecount, self.timestamping, self.reporting, self.max_untested_age)

    def name(self):
        return "Slow Blockwise Allocation Scheduler"

class SlowScheduler(object):
    '''
    This scheduler iterates over all frames in the status and tests the frame, based on the evaluation function, testing very slowly
    '''

    def __init__(self, physmem_device,frame_tests, frame_stati, kpageflags, kpagecount, timestamping, reporting, untested_age):
        '''
        Constructor
        '''
        self.frame_stati = frame_stati
        self.kpageflags = kpageflags
        self.kpagecount = kpagecount
        self.physmem_device = physmem_device
        self.frame_tests = frame_tests
        self.timestamping = timestamping
        self.max_untested_age = self.timestamping.seconds_to_timestamp(untested_age)

        self.reporting =  reporting

    def name(self):
        return "Slow Blockwise Allocation Scheduler"

    def run(self, first_frame,last_frame, allowed_sources, pfns_at_once=0,
            time_limit=0, full_time=0):

        max_blocksize = 512
        max_non_matching = 512

        cur_non_matching = 0

        attempted_pfns = 0
        total_pfns = last_frame-first_frame

        if pfns_at_once == 0:
            pfns_at_once = total_pfns

        time_per_xblock = full_time / float(total_pfns) * pfns_at_once

        test_start_time = time.time()
        block = []
        block_start_time = test_start_time
        # LZU DSLAB CHANGE

        print("pfns at once %d in %.2f ms, limit %d seconds" % (pfns_at_once, time_per_xblock * 1000, time_limit))
        tested = 0
        last_tested = 0

        # LZU DSLAB CHANGE

        for pfn in range(int(first_frame), int(last_frame)):
            frame_status = self._pfn_status(pfn)

            if (self.should_test(frame_status)):
                block.append(frame_status)
                cur_non_matching = 0
            else:
                cur_non_matching += 1

            if ((len(block) == max_blocksize) or
                (len(block) == pfns_at_once - attempted_pfns) or
                (cur_non_matching >= max_non_matching) or
                # LZU DSLAB CHANGE
                (pfn == int(last_frame)-1)):
                if (len(block) > 0 ):
                    attempted_pfns += len(block)
                    tested += self.test_frames_and_record_result(block, allowed_sources)
                    block = []
                cur_non_matching = 0

            if attempted_pfns >= pfns_at_once:

                if (time_limit != 0) and (time.time() - test_start_time > time_limit):
                    # LZU DSLAB CHANGE

                    print("---time limit per test reached")
                    break

                if len(block) > 0:
                    # LZU DSLAB CHANGE

                    print("***FEHLER*** Blocklaenge != 0 bei Schlafversuch!")

                sleeptime = time_per_xblock - (time.time() - block_start_time)

                if (time_limit != 0) and (time.time() - test_start_time + sleeptime > time_limit):
                    # LZU DSLAB CHANGE

                    print("---want to sleep %d seconds, but that would exceed the time limit" % sleeptime)
                    break

                if sleeptime > 0:
                    # LZU DSLAB CHANGE

                    print(">>> sleeping for %d seconds (time since start: %d, got %d/%d pfns)" % (sleeptime, time.time() - test_start_time, tested-last_tested, attempted_pfns))
                    time.sleep(sleeptime)
                    last_tested = tested

                block_start_time = time.time()
                attempted_pfns = 0

        return tested

    def should_test(self,frame_status):

        if frame_status.flags.any_set_in((1 << 32) | (1 << 20)):
            return False

        now = self.timestamping.timestamp()
        time_untested = now - frame_status.last_successful_test

        return  (time_untested > self.max_untested_age )

    def test_frames_and_record_result(self,frame_stati, allowed_sources):

        pfns = [frame_status.pfn for  frame_status in frame_stati]

        status_by_pfn = dict([ (frame_status.pfn, frame_status) for  frame_status in frame_stati])

        results = self._claim_pfns(pfns, allowed_sources)

        # //LZU CHANGE
        claimed_by_page = {}
        for frame in results:
            if frame.is_claimed():
                page_offset = frame.vma_offset_of_first_byte
                if (frame.pfn != frame.request.requested_pfn or
                        frame.pfn not in status_by_pfn or
                        page_offset % physmem.PAGE_SIZE != 0):
                    raise RuntimeError("claimed PFN has no valid RAMpage mapping")
                page_index = page_offset // physmem.PAGE_SIZE
                if page_index in claimed_by_page:
                    raise RuntimeError("duplicate RAMpage mapping offset")
                claimed_by_page[page_index] = frame

        num_frames_claimed = len(claimed_by_page)
        if set(claimed_by_page) != set(range(num_frames_claimed)):
            raise RuntimeError("RAMpage mapping has missing page offsets")
        claimed_physaddr = [
            claimed_by_page[index].pfn * physmem.PAGE_SIZE
            for index in range(num_frames_claimed)
        ]

        # //LZU CHANGE
        error_offsets = set()
        if num_frames_claimed > 0:
            with self.physmem_device.mmap(physmem.PAGE_SIZE * num_frames_claimed) as map:
                for test in self.frame_tests:
                    test_offsets = set(test.test(
                        map, 0, physmem.PAGE_SIZE * num_frames_claimed,
                        claimed_physaddr
                    ))
                    for bad_offset in test_offsets:
                        if (not isinstance(bad_offset, int) or
                                bad_offset < 0 or
                                bad_offset >= physmem.PAGE_SIZE * num_frames_claimed or
                                bad_offset % physmem.PAGE_SIZE != 0):
                            raise RuntimeError("tester returned an invalid page offset")
                    error_offsets.update(test_offsets)

        errors_by_page = {ofs // physmem.PAGE_SIZE for ofs in error_offsets}

        for frame in results:
            if frame.pfn in status_by_pfn:
                frame_status = status_by_pfn[frame.pfn]
                frame_status.last_claiming_attempt =  self.timestamping.timestamp()

                if frame.is_claimed():
                    frame_status.last_claiming_time_jiffies = frame.allocation_cost_jiffies
                    frame_status.last_successful_claiming_method = frame.actual_source

                    # //LZU CHANGE
                    page_index = frame.vma_offset_of_first_byte // physmem.PAGE_SIZE
                    if page_index in errors_by_page:

                        frame_status.num_errors += 1
                        frame_status.last_failed_test = self.timestamping.timestamp()
                        self.physmem_device.mark_pfn_bad(frame.pfn)
                        self._report_bad_frame(frame.pfn)
                    else:

                        frame_status.num_errors = 0
                        frame_status.last_successful_test = self.timestamping.timestamp()
                        self._report_good_frame(frame.pfn)

            else:

                # LZU DSLAB CHANGE

                self._report_not_aquired_frame(frame.pfn)

        return num_frames_claimed

    def _report_not_aquired_frame(self, pfn):
        pass

    def _report_good_frame(self, pfn):
        self.reporting.report_good_frame(pfn)

    def _report_bad_frame(self, pfn):
        self.reporting.report_bad_frame(pfn)

    def _claim_pfns(self, pfns,allowed_sources):
        requests = []
        for pfn in pfns:
            requests.append(physmem.Phys_mem_frame_request(pfn, allowed_sources))

        self.physmem_device.configure(requests)
        config = self.physmem_device.read_configuration()

        if not ( len(requests) ==  len(config) ) :

            raise RuntimeError("The result read from the physmem-device contains %d elements, but I expected %d elements! " %  (len(config),len(requests)))

        return config

    def _pfn_status(self, pfn):
        flags = self.kpageflags[pfn]
        mapcount = self.kpagecount[pfn]

        status = self.frame_stati[pfn]

        status.pfn = pfn
        status.flags =flags
        status.mapcount = mapcount

        return status

