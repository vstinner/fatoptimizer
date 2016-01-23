.. _fatoptimizer:

++++++++++++
fatoptimizer
++++++++++++

``fatoptimizer`` is a static optimizer for Python 3.6 using function
specialization with guards. It is implemented as an AST optimizer.

Optimized code requires the :ref:`fat module <fat>` at runtime if at least one
function was specialized.

Links:

* `fatoptimizer documentation
  <https://fatoptimizer.readthedocs.org/en/latest/>`_ (this documentation)
* `fatoptimizer project at GitHub
  <https://github.com/haypo/fatoptimizer>`_ (code, bug tracker)
* `fatoptimizer project at the Python Cheeseshop (PyPI)
  <https://pypi.python.org/pypi/fatoptimizer>`_ (download releases)
* `FAT Python
  <https://faster-cpython.readthedocs.org/fat_python.html>`_

fatoptimizer requires a Python 3.6 patched with the PEP 511 (``ast.Constant``,
``sys.ast_tranformers``).


Table Of Contents
=================

.. toctree::
   :maxdepth: 1

   fatoptimizer
   fat
   optimizations
   semantics
   benchmarks
   microbenchmarks
   misc
   todo
