"""
Plugin QGIS Speccount Multi-couches
Permet de traiter plusieurs couches en une seule fois avec une interface simplifiée
"""

def classFactory(iface):
    """Charge le plugin SpeccountMulti"""
    from .speccount_multi import SpeccountMultiPlugin
    return SpeccountMultiPlugin(iface)