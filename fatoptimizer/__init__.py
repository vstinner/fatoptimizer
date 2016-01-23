from .tools import pretty_dump, OptimizerError
from .config import Config
from .optimizer import ModuleOptimizer as _ModuleOptimizer
import sys


__version__ = '0.3'


def optimize(tree, filename, config):
    optimizer = _ModuleOptimizer(config, filename)
    return optimizer.optimize(tree)


class FATOptimizer:
    name = "fat"

    def __init__(self, config):
        self.config = config

    def ast_transformer(self, tree, context):
        filename = context.filename
        if sys.flags.verbose and not filename.startswith('<'):
            print("# run fatoptimizer on %s" % filename, file=sys.stderr)
        return optimize(tree, context.filename, self.config)


def _register():
    # First, import the fat module to create the copy of the builtins dict
    import fat

    import sys

    config = Config()
    config.enable_all()
    if sys.flags.verbose:
        config.logger = sys.stderr

    transformers = sys.get_code_transformers()
    # add the FAT optimizer before the peephole optimizer
    transformers.insert(0, FATOptimizer(config))
    sys.set_code_transformers(transformers)
