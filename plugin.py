import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from .speccount_multi import SpecCountMultiDialog

class SpeccountMultiPlugin:
    """Plugin principal pour le comptage multi-couches."""
    
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = 'Speccount Multi'
        self.toolbar = self.iface.addToolBar('Speccount Multi')
        self.toolbar.setObjectName('Speccount Multi')
        
    def add_action(self, icon_path, text, callback, enabled_flag=True,
                  add_to_menu=True, add_to_toolbar=True, status_tip=None,
                  whats_this=None, parent=None):
        """Ajouter une action à la barre d'outils et au menu."""
        
        icon = QIcon(icon_path) if icon_path else QIcon()
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip:
            action.setStatusTip(status_tip)
        if whats_this:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action
        
    def initGui(self):
        """Créer les éléments de l'interface graphique."""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        
        self.add_action(
            icon_path,
            text="Comptage Multi-couches",
            callback=self.run_multi_count,
            parent=self.iface.mainWindow(),
            status_tip="Lancer le comptage sur plusieurs couches"
        )
        
    def unload(self):
        """Supprime le plugin du menu et de la barre d'outils."""
        for action in self.actions:
            self.iface.removePluginMenu('Speccount Multi', action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar
        
    def run_multi_count(self):
        """Lance la boîte de dialogue de comptage multi-couches."""
        dialog = SpecCountMultiDialog(self.iface.mainWindow())
        dialog.exec_()