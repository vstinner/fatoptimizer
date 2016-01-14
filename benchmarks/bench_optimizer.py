import ast
import fatoptimizer
import time
from fatoptimizer.benchmark import format_dt

config = fatoptimizer.Config()
config.enable_all()
filename = 'x.py'
tree = ast.parse('x')

print("Optimize AST tree:")
print(ast.dump(tree))

loops = 1000

best = None
for run in range(5):
    start = time.perf_counter()
    for loop in range(loops):
        fatoptimizer.optimize(tree, filename, config)
    dt = (time.perf_counter() - start) / loops

    if best is not None:
        best = min(best, dt)
    else:
        best = dt

print("%s / call" % format_dt(dt))
