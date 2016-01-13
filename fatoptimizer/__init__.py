from .tools import pretty_dump, OptimizerError
from .config import Config
from .optimizer import ModuleOptimizer as _ModuleOptimizer


def optimize(tree, filename, config):
    optimizer = _ModuleOptimizer(config, filename)
    return optimizer.optimize(tree)


def _register():
    # First, import the fat module to create the copy of the builtins dict
    import fat

    import sys

    config = Config()
    config.enable_all()
    if sys.flags.verbose:
        config.logger = sys.stderr

    def optimizer(tree, filename):
        if sys.flags.verbose and not filename.startswith('<'):
            print("# run fatoptimizer on %s" % filename, file=sys.stderr)
        return optimize(tree, filename, config)

    sys.set_ast_transformers([(optimizer, 'fat')])
