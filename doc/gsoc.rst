+++++++++++++++++++++
Google Summer of Code
+++++++++++++++++++++

Google Summer of Code and the PSF
=================================

The `Google Summer of Code <https://summerofcode.withgoogle.com/>`_ (GSoC) "is
a global program focused on bringing more student developers into open source
software development. Students work with an open source organization on a 3
month programming project during their break from school."

The `Python Software Foundation <https://www.python.org/psf/>`_ is part of
the Google Summer of Code (GSoC) program in 2016, as previous years. See:

* `PSF GSoC projects 2016
  <https://wiki.python.org/moin/SummerOfCode/2016>`_
* `Python core projects of PSF GSoC 2016
  <https://wiki.python.org/moin/SummerOfCode/2016/python-core>`_: this page
  mentions the GSoC project on FAT Python (but this page is more complete).


FAT Python
==========

FAT Python is a new static optimizer for Python 3.6, it specializes functions
and use guards to decide if specialized code can be called or not. See `FAT
Python homepage <https://faster-cpython.readthedocs.io/fat_python.html>`_ and
the `slides of my talk at FOSDEM 2016
<https://github.com/vstinner/conf/raw/master/2016-FOSDEM/fat_python.pdf>`_ for
more information.

The design is *inspired* by JIT compilers, but is simpler. FAT Python has been
designed to be able to merge changes required to use FAT Python into CPython
3.6. The expected use case is to compile modules and applications
ahead-of-time, so the performance of the optimizer itself don't matter much.

FAT Python is made of different parts:

* CPython 3.6
* fat module: fast guards implemented in C
* fatoptimizer module: the static optimizer implemented as an AST optimizer.
  It produces specialized functions of functions using guards.
* PEP 509 (dict version): patch required by the fat module to implement fast
  guards on Python namespaces
* PEP 510 (function specialization): private C API to add specialized code
  to Python functions
* PEP 511 (API for AST optimizers): new Python API to register an AST optimizer

Status at March 2016:

* First patches to implement AST optimizers have already been merged in CPython
  3.6
* fat and fatoptimizer have been implemented, are fully functional and have
  unit tests
* early benchmarks don't show major speedup on "The Grand Unified Python
  Benchmark Suite"
* fatoptimizer is quite slow
* PEP 509 need to be modified to make the dictionary versions globally unique.
  PEP 509 is required by the promising `Speedup method calls 1.2x
  <https://bugs.python.org/issue26110>`_ change written by Yury Selivanov.
  This change can help to get this PEP accepted.
* PEP 511 is still a work-in-progress, it's even unclear if the whole PEP
  is required. It only makes the usage of FAT Python more practical. It avoids
  conflicts on .pyc files using the ``-o`` command line option proposed in the
  PEP.
* PEP 509, 510 and 511 are basically blocked by an expectation on concrete
  speedup


FAT Python GSoC Roadmap
=======================

GSoC takes 4 months, the exact planning is not defined yet.

Goal
----

The overall goal is to enhance FAT Python to get concrete speedup on the
benchmark suite and on applications.


Requirements
------------

* All requirements of the GSoC program! (like being available during
  the 4 months of the GSoC program)
* Able to read and write technical english
* Better if already the student worked remotely on a free software before
* Good knowledge of the Python programming language
* (Optional?) Basic knowledge of how compilers are implemented
* (Optional?) Basic knowledge of static optimizations like constant folding


Milestone 0 to select the student
---------------------------------

fatoptimizer:

* Download `fatoptimizer <https://fatoptimizer.readthedocs.io/>`_ and run tests::

    git clone https://github.com/vstinner/fatoptimizer
    cd fatoptimizer
    python3 test_fatoptimizer.py

* Read the `fatoptimizer documentation <https://fatoptimizer.readthedocs.io/>`_
* Pick a simple task in the :ref:`fatoptimizer TODO list <todo>` and send a
  pull request
* MANDATORY: Submit a final PDF proposal: see
  https://wiki.python.org/moin/SummerOfCode/2016 for a template

Optional:

* Download and compile FAT Python:
  https://faster-cpython.readthedocs.io/fat_python.html#getting-started
* Run Python test suite of FAT Python


Milestone 1
-----------

Discover FAT Python.

* Select a set of benchmarks
* Run benchmarks to have a reference for performances (better: write a script
  for that)
* Implement the most easy optimizations of the :ref:`TODO list <todo>`
  (like remaining constant folding optimizations)
* Run the full Python test suite with FAT Python
* Run real applications like Django with FAT Python to identify bugs
* Propose fixes or workaround for bugs

Goal: have at least one new optimization merged into fatoptimizer.

Milestone 2
-----------

Function inlining.

* Test the existing (basic) implementation of function inlining
* Fix function inlining
* Enhance function inlining to use it in more cases
* Wider tests of the new features
* Fix bugs

Goal: make function inlining usable with the default config without breaking
the Python test suite, even if it's only a subset of the feature.


Milestone 3
-----------

Remove useless variables. For example, remove ``x`` in
``def func(): x = 1; return 2``.

* Add configuration option to enable this optimization
* Write an unit test for the expected behaviour
* Implement algorithm to compute where and when a variable is alive or not
* Use this algorithm to find dead variables and then remove them
* Wider tests of the new features
* Fix bugs

Goal: remove useless variables with the default config without breaking the
Python test suite, even if it's only a subset of the feature.


Milestone 4 (a)
---------------

Detect pure function, first subpart: implement it manually.

* Add an option to __fatoptimizer__ module configuration to explicitly declare
  constants
* Write a patch to declare some constants in the Python standard library
* Add an option to __fatoptimizer__ module configuration to explicitly declare
  pure functions
* Write a patch to declare some pure functions in the Python standard library,
  ex: os.path._getsep().

Goal: annotate a few constants and pure functions in the Python standard
library and ensure that they are optimized.

Milestone 4 (b)
---------------

Detect pure function, second and last subpart: implement automatic detection.

* Write a safe heuristic to detect pure functions using a small whitelist of
  instructions which are known to be pure
* Wider tests of the new features
* Fix bugs
* Extend the whitelist, add more and more instructions
* Run tests
* Fix bugs
* Iterate until the whitelist is considered big enough?
* Maybe design a better algorithm than a white list?

See also pythran which already implemented this feature :-)

Goal: detect that os.path._getsep() is pure.

Goal 2, optional: inline os.path._getsep() in isabs().


More milestones?
----------------

The exact planning will be adapted depending on the speed of the student,
the availability of mentors, etc.

