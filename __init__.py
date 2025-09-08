from .selectchoice import LayerChoiceSelectPlugin


def classFactory(iface):
    return LayerChoiceSelectPlugin(iface)
