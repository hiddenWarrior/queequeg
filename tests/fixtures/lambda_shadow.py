from tests.fixtures.cross_file_b import shared_helper


def uses_lambda():
    # lambda param 'shared_helper' shadows the import — should NOT be traced as dep
    transform = lambda shared_helper: shared_helper * 2
    return transform(5)
