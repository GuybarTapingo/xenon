'''This module contains Xenon's main functionality. Only the
:func:`~xenon.core.analyze` function should be used directly.
'''

from collections import defaultdict

from radon.complexity import cc_rank, SCORE
from radon.cli import Config
from radon.cli.harvest import CCHarvester


def analyze(args, logger):
    '''Analyze the files as specified in *args*. Logging is done through the
    given *logger*.
    The *args* object should have the following attributes:

        * ``path``: a list of files to analyze.
        * ``exclude`` and ``ignore``: the patterns specifying which files to
            exclude and which directories to ignore.
        * ``no_assert``: if ``True``, ``assert`` statements will not be counted
            towards increasing the cyclomatic complexity.
        * ``absolute``, ``modules`` and ``average``: the threshold for the
            complexity.
    '''
    config = Config(
        exclude=args.exclude,
        ignore=args.ignore,
        order=SCORE,
        no_assert=args.no_assert,
        show_closures=False,
        min='A',
        max='F',
    )
    h = CCHarvester(args.path, config)
    results = h._to_dicts()
    return find_infractions(args, logger, results), results


def build_blocks_to_ignore(args):
    '''Build a dict from module name to a list of blocks in that module to ignore.

    Read the data from args.ignore_blocks which is a list of blocks separated by ",".
    The format of a block is "<module_name>:<block_name>".
    '''
    if not args.ignore_blocks:
        return {}

    blocks_to_ignore = defaultdict(list)

    for block_to_ignore in args.ignore_blocks.split(','):
        module_name, block_name = block_to_ignore.split(':')
        blocks_to_ignore[module_name.strip()].append(block_name.strip())

    return blocks_to_ignore


def av(n, m):
    '''Compute n/m if ``m != 0`` or otherwise return 0.'''
    return n / m if m != 0 else 0


def check(rank, default=None):
    '''Check whether `rank` is greater than `default`.'''
    return rank > default.upper() if default is not None else False


def find_infractions(args, logger, results):
    '''Analyze the results and find if the thresholds are surpassed.

    *args* and *logger* are the same as in :func:`~xenon.core.analyze`, while
    *results* is a dictionary holding the results of the complexity analysis.

    The number of infractions with respect to the threshold values is returned.
    '''
    blocks_to_ignore = build_blocks_to_ignore(args)
    infractions = 0
    module_averages = []
    total_cc = 0.
    total_blocks = 0
    for module, blocks in results.items():
        module_cc = 0.
        if isinstance(blocks, dict) and blocks.get('error'):
            logger.warning('cannot parse %s: %s', module, blocks['error'])
            continue
        for block in blocks:
            module_cc += block['complexity']
            r = cc_rank(block['complexity'])
            if check(r, args.absolute) and block['name'] not in blocks_to_ignore.get(module, []):
                logger.error('block "%s:%s %s" has a rank of %s', module,
                             block['lineno'], block['name'], r)
                infractions += 1
        module_averages.append((module, av(module_cc, len(blocks))))
        total_cc += module_cc
        total_blocks += len(blocks)

    av_cc = av(total_cc, total_blocks)
    ar = cc_rank(av_cc)

    if args.averagenum is not None and av_cc > args.averagenum:
        logger.error('total average complexity is %s', av_cc)
        infractions += 1

    if check(ar, args.average):
        logger.error('average complexity is ranked %s', ar)
        infractions += 1
    for module, ma in module_averages:
        mar = cc_rank(ma)
        if check(mar, args.modules):
            logger.error('module %r has a rank of %s', module, mar)
            infractions += 1
    return infractions
