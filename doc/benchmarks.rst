++++++++++
Benchmarks
++++++++++

fatoptimizer is not ready for macro benchmarks. Important optimizations like
function inlining are still missing. See the :ref:`fatoptimizer TODO list
<todo>`.

See :ref:`Microbenchmarks <microbench>`.


The Grand Unified Python Benchmark Suite
========================================

Project hosted at https://hg.python.org/benchmarks

2016-01-22, don't specialized nested functions anymore::

    $ time python3 ../benchmarks/perf.py ../default/python ../fatpython/python 2>&1|tee log
    INFO:root:Automatically selected timer: perf_counter
    INFO:root:Running `../fatpython/python ../benchmarks/lib3/2to3/2to3 -f all ../benchmarks/lib/2to3`
    INFO:root:Running `../fatpython/python ../benchmarks/lib3/2to3/2to3 -f all ../benchmarks/lib/2to3` 1 time
    INFO:root:Running `../default/python ../benchmarks/lib3/2to3/2to3 -f all ../benchmarks/lib/2to3`
    INFO:root:Running `../default/python ../benchmarks/lib3/2to3/2to3 -f all ../benchmarks/lib/2to3` 1 time
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_chameleon_v2.py -n 50 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_chameleon_v2.py -n 50 --timer perf_counter`
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_django_v3.py -n 50 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_django_v3.py -n 50 --timer perf_counter`
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_pickle.py -n 50 --timer perf_counter --use_cpickle pickle`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_pickle.py -n 50 --timer perf_counter --use_cpickle pickle`
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_pickle.py -n 50 --timer perf_counter --use_cpickle unpickle`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_pickle.py -n 50 --timer perf_counter --use_cpickle unpickle`
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_json_v2.py -n 50 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_json_v2.py -n 50 --timer perf_counter`
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_json.py -n 50 --timer perf_counter json_load`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_json.py -n 50 --timer perf_counter json_load`
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_nbody.py -n 50 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_nbody.py -n 50 --timer perf_counter`
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_regex_v8.py -n 50 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_regex_v8.py -n 50 --timer perf_counter`
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_tornado_http.py -n 100 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_tornado_http.py -n 100 --timer perf_counter`
    [ 1/10] 2to3...
    [ 2/10] chameleon_v2...
    [ 3/10] django_v3...
    [ 4/10] fastpickle...
    [ 5/10] fastunpickle...
    [ 6/10] json_dump_v2...
    [ 7/10] json_load...
    [ 8/10] nbody...
    [ 9/10] regex_v8...
    [10/10] tornado_http...

    Report on Linux smithers 4.2.8-300.fc23.x86_64 #1 SMP Tue Dec 15 16:49:06 UTC 2015 x86_64 x86_64
    Total CPU cores: 8

    ### 2to3 ###
    7.232935 -> 7.078553: 1.02x faster

    ### chameleon_v2 ###
    Min: 5.740738 -> 5.642322: 1.02x faster
    Avg: 5.805132 -> 5.669008: 1.02x faster
    Significant (t=5.61)
    Stddev: 0.17073 -> 0.01766: 9.6699x smaller

    ### fastpickle ###
    Min: 0.448408 -> 0.454956: 1.01x slower
    Avg: 0.450220 -> 0.469483: 1.04x slower
    Significant (t=-8.28)
    Stddev: 0.00364 -> 0.01605: 4.4102x larger

    ### fastunpickle ###
    Min: 0.546227 -> 0.582611: 1.07x slower
    Avg: 0.554405 -> 0.602790: 1.09x slower
    Significant (t=-6.05)
    Stddev: 0.01496 -> 0.05453: 3.6461x larger

    ### regex_v8 ###
    Min: 0.042338 -> 0.043736: 1.03x slower
    Avg: 0.042663 -> 0.044073: 1.03x slower
    Significant (t=-4.09)
    Stddev: 0.00173 -> 0.00172: 1.0021x smaller

    ### tornado_http ###
    Min: 0.260895 -> 0.274085: 1.05x slower
    Avg: 0.265663 -> 0.277511: 1.04x slower
    Significant (t=-11.26)
    Stddev: 0.00988 -> 0.00360: 2.7464x smaller

    The following not significant results are hidden, use -v to show them:
    django_v3, json_dump_v2, json_load, nbody.

    real	20m7.994s
    user	19m44.016s
    sys	0m22.894s

2016-01-21::

    $ time python3 ../benchmarks/perf.py ../default/python ../fatpython/python
    INFO:root:Automatically selected timer: perf_counter
    [ 1/10] 2to3...
    INFO:root:Running `../fatpython/python ../benchmarks/lib3/2to3/2to3 -f all ../benchmarks/lib/2to3`
    INFO:root:Running `../fatpython/python ../benchmarks/lib3/2to3/2to3 -f all ../benchmarks/lib/2to3` 1 time
    INFO:root:Running `../default/python ../benchmarks/lib3/2to3/2to3 -f all ../benchmarks/lib/2to3`
    INFO:root:Running `../default/python ../benchmarks/lib3/2to3/2to3 -f all ../benchmarks/lib/2to3` 1 time
    [ 2/10] chameleon_v2...
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_chameleon_v2.py -n 50 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_chameleon_v2.py -n 50 --timer perf_counter`
    [ 3/10] django_v3...
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_django_v3.py -n 50 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_django_v3.py -n 50 --timer perf_counter`
    [ 4/10] fastpickle...
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_pickle.py -n 50 --timer perf_counter --use_cpickle pickle`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_pickle.py -n 50 --timer perf_counter --use_cpickle pickle`
    [ 5/10] fastunpickle...
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_pickle.py -n 50 --timer perf_counter --use_cpickle unpickle`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_pickle.py -n 50 --timer perf_counter --use_cpickle unpickle`
    [ 6/10] json_dump_v2...
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_json_v2.py -n 50 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_json_v2.py -n 50 --timer perf_counter`
    [ 7/10] json_load...
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_json.py -n 50 --timer perf_counter json_load`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_json.py -n 50 --timer perf_counter json_load`
    [ 8/10] nbody...
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_nbody.py -n 50 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_nbody.py -n 50 --timer perf_counter`
    [ 9/10] regex_v8...
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_regex_v8.py -n 50 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_regex_v8.py -n 50 --timer perf_counter`
    [10/10] tornado_http...
    INFO:root:Running `../fatpython/python ../benchmarks/performance/bm_tornado_http.py -n 100 --timer perf_counter`
    INFO:root:Running `../default/python ../benchmarks/performance/bm_tornado_http.py -n 100 --timer perf_counter`

    Report on Linux smithers 4.2.8-300.fc23.x86_64 #1 SMP Tue Dec 15 16:49:06 UTC 2015 x86_64 x86_64
    Total CPU cores: 8

    ### 2to3 ###
    6.969972 -> 7.362033: 1.06x slower

    ### chameleon_v2 ###
    Min: 5.686547 -> 5.945011: 1.05x slower
    Avg: 5.731851 -> 5.976754: 1.04x slower
    Significant (t=-21.46)
    Stddev: 0.06645 -> 0.04580: 1.4511x smaller

    ### fastpickle ###
    Min: 0.489443 -> 0.448850: 1.09x faster
    Avg: 0.518914 -> 0.458638: 1.13x faster
    Significant (t=6.48)
    Stddev: 0.05688 -> 0.03304: 1.7218x smaller

    ### fastunpickle ###
    Min: 0.598339 -> 0.559612: 1.07x faster
    Avg: 0.604129 -> 0.564821: 1.07x faster
    Significant (t=13.55)
    Stddev: 0.01493 -> 0.01408: 1.0601x smaller

    ### json_dump_v2 ###
    Min: 2.794058 -> 4.456882: 1.60x slower
    Avg: 2.806195 -> 4.467750: 1.59x slower
    Significant (t=-801.42)
    Stddev: 0.00722 -> 0.01276: 1.7678x larger

    ### regex_v8 ###
    Min: 0.041685 -> 0.050890: 1.22x slower
    Avg: 0.042082 -> 0.051579: 1.23x slower
    Significant (t=-26.94)
    Stddev: 0.00177 -> 0.00175: 1.0105x smaller

    ### tornado_http ###
    Min: 0.258212 -> 0.272552: 1.06x slower
    Avg: 0.263689 -> 0.280610: 1.06x slower
    Significant (t=-8.59)
    Stddev: 0.01614 -> 0.01130: 1.4282x smaller

    The following not significant results are hidden, use -v to show them:
    django_v3, json_load, nbody.

    real	21m53.511s
    user	21m29.279s
    sys	0m23.055s
