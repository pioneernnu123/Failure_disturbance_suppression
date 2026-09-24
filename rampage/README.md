# RISC-V 内存失效扰动抑制

This repository contains the RAMpage online memory tester for Linux, which we
developed on the basis of
[Jens Neuhalfen's memtester](https://github.com/neuhalje/kernel-memtest).

## Basic Setup

These steps are required to setup and run RAMpage:

* You need to patch the Linux kernel sources in order to export a few
  more symbols needed by the module.  You can find a patch matching
  the Linux 3.5 sources in patches/kernelpatch-rampage-3.5-declone.diff,
  but with some luck (and if the kernel memory management hasn't
  changed too much) this should be portable to newer kernel versions
  with little to no effort.  The kernel should be configured by moving
  /config-rampage-final-2.6.35 to $kernelsource/.config and running
  ```make oldconfig```.  (RAMpage only works with an x86-64 kernel at the moment.)

* After having booted the patched kernel, you need to build and insert
  the kernel module by entering module/ and running ```./rebuild.sh```.

  <!-- //LZU CHANGE -->
  All shell scripts in this repository use LF line endings.  If an older copy
  transferred from Windows reports `cannot execute: required file not found`,
  repair that copy before running it again:

        cd rampage/module
        sed -i 's/\r$//' rebuild.sh
        chmod +x rebuild.sh
        ./rebuild.sh

* Then you need to prepare the userspace memory tester C extensions:

        cd rampage/userspace/tester  
        make && cp build/*/*.so .  
        cd ..

* RAMpage should now be ready to run, for example:

        ./main.py -a blockwise --run-time 86400 --retest-time 86400 -4 -t mt86* -f 5120 \
          --enable-p4-claimers=buddy,hotplug-claim,shaking

  ```./main.py --help``` gives an explanation for the parameters and switches.

<!-- //LZU CHANGE -->
## Change memtester injection type while RAMpage is running

Build and install the memtester binary from this checkout on the Linux target
before starting RAMpage.  The older installed binary does not understand the
RAMpage mapping options:

        cd /path/to/Failure_disturbance_suppression/memtester-master
        make
        python3 test_rampage_fd.py
        sudo install -m 755 memtester /usr/local/bin/memtester

Start the continuous memory test in the first terminal.  The initial injection
type is `0` unless `--memtester-inject-type` is supplied:

        cd /path/to/Failure_disturbance_suppression/rampage/userspace
        python3 main.py -t memtester -a slow --frames-per-check 50 \
          --retest-time 0 --no-delay \
          --memtester-args="-i 5" --memtester-inject-type 0 \
          --logfile=memtester-slow.log

Keep that process running.  In a second terminal, start the controller:

        cd /path/to/Failure_disturbance_suppression/rampage/userspace
        python3 injection_control.py

Enter a number from `0` to `7` whenever the injection type needs to change.
The new type is used by the next memtester invocation.  Stop the continuous
memory test with `Ctrl+C` in the first terminal.  Each memtester invocation
records its current injection number and name in
`rampage/userspace/memtester_execution_details.log` in this checkout.

In RAMpage mode, memtester inherits the current `/dev/phys_mem` session and
tests each claimed page in that mapping.  `-i 5` selects page 5 within the
current claimed batch, starting at page 0; a shorter batch has no page 5 to
inject.  The detailed log records each mapped page's PFN and whether a
failure occurred.  Every detected failure follows RAMpage's existing bad-page
handling and is marked by the kernel module.  Testing each page independently
provides an exact page-to-PFN mapping; it does not exercise address aliases
between different pages in the batch.

Be aware that RAMpage is a prototype, not production-ready software.
One detail you certainly will have to change before using it in a multiuser
environment is the access permissions to /proc/kpagecount and /proc/kpageflags
(rampage/module/rebuild.sh currently chmod's these to 0444) and especially the
module's own /proc/phys_mem (currently 0777).

Patches and ports to new kernel versions and other kernels welcome!

## Publications

A detailed description, and measurements on both effectiveness and efficiency,
can be found in the following two publications:

* H. Schirmeier, J. Neuhalfen, I. Korb, O. Spinczyk, and M. Engel.
  [RAMpage: Graceful degradation management for memory errors in commodity
  Linux servers](https://ess.cs.tu-dortmund.de/~hsc/Publications/files/PRDC-FAST-2011-Schirmeier.pdf).
  In *Proceedings of the 17th IEEE Pacific Rim International Symposium on
  Dependable Computing (PRDC '11)*, pages 89-98, Pasadena, CA, USA, Dec. 2011.
  IEEE Computer Society Press.

* H. Schirmeier, I. Korb, O. Spinczyk, and M. Engel. [Efficient online memory
  error assessment and circumvention for Linux with
  RAMpage](https://ess.cs.tu-dortmund.de/~hsc/Publications/files/IJCCBS-2013-Schirmeier.pdf).
  *International Journal of Critical Computer-Based Systems*,
  4(3):227-247, 2013.  Special Issue on PRDC 2011 Dependable Architecture and
  Analysis.

The code in this repository is licensed under the GNU General Public License
(GPL), Version 2.
