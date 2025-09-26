"""
Plugin QGIS pour le comptage des espèces à partir de TAXREF - Version Multi-couches
"""

import os
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QListWidget, QLabel, QComboBox, QProgressBar,
                                QListWidgetItem, QAbstractItemView, QMessageBox,
                                QGroupBox, QTableWidget, QTableWidgetItem,
                                QHeaderView)
from qgis.PyQt.QtCore import Qt
from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature, QgsFields, QgsField,
                      QgsMessageLog, Qgis, QgsVectorFileWriter)
from qgis.gui import QgsFileWidget
from qgis.PyQt.QtCore import QMetaType
from .utils import (get_cd_ref_from_cd_nom, get_tri_rang, get_taxsup)
from functools import reduce
import pandas as pd


class ResultsSummaryDialog(QDialog):
    """Fenêtre récapitulative des résultats de traitement."""
    
    def __init__(self, results_data, output_folder=None, parent=None):
        super().__init__(parent)
        self.results_data = results_data
        self.output_folder = output_folder
        self.setWindowTitle("Récapitulatif des traitements")
        self.setModal(True)
        self.resize(800, 600)
        self.setup_ui()
        
    def setup_ui(self):
        """Créer l'interface utilisateur."""
        layout = QVBoxLayout(self)
        
        # Titre
        title_label = QLabel("Récapitulatif des traitements par couche")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Tableau des résultats
        self.results_table = QTableWidget()
        headers = [
            "Couche d'entrée", 
            "Couche de sortie", 
            "Nb espèces", 
            "Nb imprécis", 
            "Nb sans correspondance",
            "Fichier de sortie"
        ]
        self.results_table.setColumnCount(len(headers))
        self.results_table.setHorizontalHeaderLabels(headers)
        self.results_table.setRowCount(len(self.results_data))
        
        # Remplir le tableau
        for row, (input_layer, result_info) in enumerate(self.results_data.items()):
            if isinstance(result_info, dict):  # Traitement réussi
                self.results_table.setItem(row, 0, QTableWidgetItem(input_layer))
                self.results_table.setItem(row, 1, QTableWidgetItem(result_info['output_layer_name']))
                self.results_table.setItem(row, 2, QTableWidgetItem(str(result_info['species_count'])))
                self.results_table.setItem(row, 3, QTableWidgetItem(str(result_info['imprecis_count'])))
                self.results_table.setItem(row, 4, QTableWidgetItem(str(result_info['no_matching_rank_count'])))
                
                output_file = result_info.get('output_path', 'Couche temporaire')
                if output_file and output_file != 'Couche temporaire':
                    output_file = os.path.basename(output_file)
                self.results_table.setItem(row, 5, QTableWidgetItem(output_file))
            else:  # Erreur
                self.results_table.setItem(row, 0, QTableWidgetItem(input_layer))
                self.results_table.setItem(row, 1, QTableWidgetItem("ERREUR"))
                self.results_table.setItem(row, 2, QTableWidgetItem("-"))
                self.results_table.setItem(row, 3, QTableWidgetItem("-"))
                self.results_table.setItem(row, 4, QTableWidgetItem("-"))
                self.results_table.setItem(row, 5, QTableWidgetItem("-"))
        
        # Ajuster la taille des colonnes
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table)
        
        # Statistiques globales
        stats_group = QGroupBox("Statistiques globales")
        stats_layout = QVBoxLayout(stats_group)
        
        successful_treatments = [r for r in self.results_data.values() if isinstance(r, dict)]
        total_species = sum(r['species_count'] for r in successful_treatments)
        total_imprecis = sum(r['imprecis_count'] for r in successful_treatments)
        total_no_match = sum(r['no_matching_rank_count'] for r in successful_treatments)
        
        stats_text = f"""
        Couches traitées avec succès : {len(successful_treatments)} / {len(self.results_data)}
        Total espèces trouvées : {total_species}
        Total observations imprécises : {total_imprecis}
        Total observations sans correspondance : {total_no_match}
        """
        
        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet("font-family: monospace; margin: 10px;")
        stats_layout.addWidget(stats_label)
        layout.addWidget(stats_group)
        
        # Boutons
        button_layout = QHBoxLayout()
        
        # Bouton pour ouvrir le dossier de sortie
        if self.output_folder and self.output_folder not in ["Selectionnez un dossier de sortie si besoin", ""]:
            self.open_folder_btn = QPushButton("Ouvrir le dossier de sortie")
            self.open_folder_btn.clicked.connect(self.open_output_folder)
            button_layout.addWidget(self.open_folder_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Fermer")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
    def open_output_folder(self):
        """Ouvrir le dossier de sortie dans l'explorateur."""
        if not self.output_folder or not os.path.exists(self.output_folder):
            QMessageBox.warning(self, "Attention", "Le dossier de sortie n'existe pas.")
            return
            
        try:
            os.startfile(self.output_folder)
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Impossible d'ouvrir le dossier de sortie : {str(e)}")


class SpecCountMultiDialog(QDialog):
    """Boîte de dialogue pour le comptage multi-couches."""
    
    def __init__(self, parent=None, taxref_df=None, taxrank_df=None):
        super().__init__(parent)
        self.setWindowTitle("Comptage d'espèces - Multi-couches")
        self.setModal(True)
        self.resize(600, 500)
        
        # Variables
        self.selected_layers = []
        self.taxref_df = taxref_df
        self.taxrank_df = taxrank_df
        
        # Interface
        self.setup_ui()
        self.load_data()
        self.populate_layers()
        self.populate_taxref_fields()
        
    def setup_ui(self):
        """Créer l'interface utilisateur."""
        layout = QVBoxLayout(self)
        
        # Groupe de sélection des couches
        layer_group = QGroupBox("Sélection des couches")
        layer_layout = QVBoxLayout(layer_group)
        
        # Label d'instruction
        instruction_label = QLabel("Sélectionnez les couches à traiter (maintenez Ctrl pour sélection multiple) :")
        layer_layout.addWidget(instruction_label)
        
        # Liste des couches
        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(QAbstractItemView.MultiSelection)
        layer_layout.addWidget(self.layer_list)
        
        # Boutons de sélection
        button_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Tout sélectionner")
        self.select_all_btn.clicked.connect(self.select_all_layers)
        self.clear_selection_btn = QPushButton("Tout désélectionner")
        self.clear_selection_btn.clicked.connect(self.clear_selection)
        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.clear_selection_btn)
        button_layout.addStretch()
        layer_layout.addLayout(button_layout)
        
        layout.addWidget(layer_group)
        
        # Groupe de paramètres
        param_group = QGroupBox("Paramètres")
        param_layout = QVBoxLayout(param_group)
        
        # Champ cd_nom
        param_layout.addWidget(QLabel("Champ contenant les identifiants taxonomiques (cd_nom) :"))
        self.cd_nom_combo = QComboBox()
        self.cd_nom_combo.setEditable(True)
        self.cd_nom_combo.addItems(["cd_nom", "CD_NOM", "taxon_id", "espece_id"])
        param_layout.addWidget(self.cd_nom_combo)
        
        # Rang taxonomique
        param_layout.addWidget(QLabel("Rang taxonomique souhaité :"))
        self.rank_combo = QComboBox()
        rank_choices = [
            'Règne (Regnum)',
            'Embranchement (Phylum)', 
            'Division',
            'Classe (Classis)',
            'Ordre (Ordo)',
            'Famille (Familia)',
            'Genre (Genus)',
            'Espèce (Species)',
            'Sous-Espèce',
            'Variété',
            'Forme'
        ]
        self.rank_combo.addItems(rank_choices)
        self.rank_combo.setCurrentText('Espèce (Species)')
        param_layout.addWidget(self.rank_combo)
        
        # Option de sauvegarde
        self.folder_widget = QgsFileWidget()
        self.folder_widget.setStorageMode(QgsFileWidget.GetDirectory)  # on veut un dossier
        self.folder_widget.setFilePath("Selectionnez un dossier de sortie si besoin")  # vide par défaut
        # self.folder_widget.setCaption("Création d'une couche temporaire")  # texte de base
        param_layout.addWidget(self.folder_widget)

        layout.addWidget(param_group)
        
        # Groupe de sélection des champs TAXREF
        fields_group = QGroupBox("Champs TAXREF à inclure dans les résultats")
        fields_layout = QVBoxLayout(fields_group)
        
        # Instructions
        fields_instruction = QLabel("Sélectionnez les champs TAXREF à inclure (maintenez Ctrl pour sélection multiple) :")
        fields_layout.addWidget(fields_instruction)
        
        # Liste des champs TAXREF
        self.taxref_fields_list = QListWidget()
        self.taxref_fields_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.taxref_fields_list.setMaximumHeight(200)
        fields_layout.addWidget(self.taxref_fields_list)
        
        # Boutons pour les champs
        fields_button_layout = QHBoxLayout()
        self.select_default_fields_btn = QPushButton("Sélection par défaut")
        self.select_default_fields_btn.clicked.connect(self.select_default_taxref_fields)
        self.select_all_fields_btn = QPushButton("Tous les champs")
        self.select_all_fields_btn.clicked.connect(self.select_all_taxref_fields)
        self.clear_fields_btn = QPushButton("Aucun champ")
        self.clear_fields_btn.clicked.connect(self.clear_taxref_fields)
        
        fields_button_layout.addWidget(self.select_default_fields_btn)
        fields_button_layout.addWidget(self.select_all_fields_btn)
        fields_button_layout.addWidget(self.clear_fields_btn)
        fields_button_layout.addStretch()
        fields_layout.addLayout(fields_button_layout)
        
        layout.addWidget(fields_group)
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Boutons d'action
        button_layout = QHBoxLayout()
        self.process_btn = QPushButton("Traiter les couches")
        self.process_btn.clicked.connect(self.process_layers)
        self.close_btn = QPushButton("Fermer")
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addStretch()
        button_layout.addWidget(self.process_btn)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
        
    def load_data(self):
        """Charger les données TAXREF."""
        if self.taxref_df is not None and self.taxrank_df is not None:
            return  # Les données sont déjà chargées
        try:
            plugin_dir = os.path.dirname(__file__)
            data_dir = os.path.join(plugin_dir, 'data')
            
            taxref_path = os.path.join(data_dir, 'taxref.parquet')
            taxrank_path = os.path.join(data_dir, 'taxrank.parquet')
            
            if os.path.exists(taxref_path):
                self.taxref_df = pd.read_parquet(taxref_path)
                QgsMessageLog.logMessage(f"TAXREF chargé : {len(self.taxref_df)} enregistrements", 
                                       "Speccount", Qgis.Info)
            else:
                QgsMessageLog.logMessage(f"Fichier TAXREF non trouvé : {taxref_path}", 
                                       "Speccount", Qgis.Critical)
                
            if os.path.exists(taxrank_path):
                self.taxrank_df = pd.read_parquet(taxrank_path)
                QgsMessageLog.logMessage(f"TAXRANK chargé : {len(self.taxrank_df)} enregistrements", 
                                       "Speccount", Qgis.Info)
            else:
                QgsMessageLog.logMessage(f"Fichier TAXRANK non trouvé : {taxrank_path}", 
                                       "Speccount", Qgis.Critical)
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur lors du chargement des données : {str(e)}", 
                                   "Speccount", Qgis.Critical)
            
    def populate_layers(self):
        """Remplir la liste des couches vectorielles."""
        self.layer_list.clear()
        
        # Récupérer toutes les couches vectorielles du projet
        layers = QgsProject.instance().mapLayers().values()
        vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]

        for layer in vector_layers:
            item = QListWidgetItem(layer.name())
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)  # rend l'item checkable
            item.setCheckState(Qt.Unchecked)  # état initial
            self.layer_list.addItem(item)
            
    def select_all_layers(self):
        """Sélectionner toutes les couches."""
        for i in range(self.layer_list.count()):
            self.layer_list.item(i).setCheckState(Qt.Checked)
            
    def clear_selection(self):
        """Désélectionner toutes les couches."""
        for i in range(self.layer_list.count()):
            self.layer_list.item(i).setCheckState(Qt.Unchecked)

    def get_selected_layers(self):
        """Récupérer les couches sélectionnées."""
        selected_layers = []
        for i in range(self.layer_list.count()):
            item = self.layer_list.item(i)
            if item.checkState() == Qt.Checked:
                layer_name = item.text()
                layer = QgsProject.instance().mapLayersByName(layer_name)[0]
                selected_layers.append(layer)
        return selected_layers
    
    def populate_taxref_fields(self):
        """Remplir la liste des champs TAXREF disponibles."""
        self.taxref_fields_list.clear()
        
        if self.taxref_df is not None:
            # Exclure les champs techniques et garder les champs utiles
            excluded_fields = {'cd_nom', 'cd_ref', 'cd_taxsup', 'id_rang'}
            available_fields = [col for col in self.taxref_df.columns if col not in excluded_fields]
            
            for field in sorted(available_fields):
                item = QListWidgetItem(field)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)  # rend l'item checkable
                self.taxref_fields_list.addItem(item)
            
            # Sélectionner les champs par défaut
            self.select_default_taxref_fields()
    
    def select_default_taxref_fields(self):
        """Sélectionner les champs TAXREF par défaut."""
        default_fields = [
            'nom_complet', 'nom_vern'
        ]
        
        for i in range(self.taxref_fields_list.count()):
            item = self.taxref_fields_list.item(i)
            if item.text() in default_fields:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def select_all_taxref_fields(self):
        """Sélectionner tous les champs TAXREF."""
        for i in range(self.taxref_fields_list.count()):
            self.taxref_fields_list.item(i).setCheckState(Qt.Checked)
    
    def clear_taxref_fields(self):
        """Désélectionner tous les champs TAXREF."""
        for i in range(self.taxref_fields_list.count()):
            self.taxref_fields_list.item(i).setCheckState(Qt.Unchecked)

    def get_selected_taxref_fields(self):
        """Récupérer les champs TAXREF sélectionnés."""
        selected_fields = []
        for i in range(self.taxref_fields_list.count()):
            item = self.taxref_fields_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_fields.append(item.text())
        return selected_fields
        
    def process_layers(self):
        """Traiter les couches sélectionnées."""
        selected_layers = self.get_selected_layers()
        
        if not selected_layers:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner au moins une couche.")
            return
            
        if self.taxref_df is None or self.taxrank_df is None:
            QMessageBox.critical(self, "Erreur", "Les données TAXREF ne sont pas chargées.")
            return
            
        cd_nom_field = self.cd_nom_combo.currentText()
        rank_text = self.rank_combo.currentText()
        selected_taxref_fields = self.get_selected_taxref_fields()
        
        # if not selected_taxref_fields:
        #     QMessageBox.warning(self, "Attention", "Veuillez sélectionner au moins un champ TAXREF à inclure.")
        #     return
        
        # Mapper le rang sélectionné
        rank_mapping = {
            'Règne (Regnum)': 20,
            'Embranchement (Phylum)': 40,
            'Division': 50,
            'Classe (Classis)': 80,
            'Ordre (Ordo)': 140,
            'Famille (Familia)': 180,
            'Genre (Genus)': 220,
            'Espèce (Species)': 290,
            'Sous-Espèce': 320,
            'Variété': 340,
            'Forme': 360
        }
        wanted_rank = rank_mapping.get(rank_text, 290)
        
        # Afficher la barre de progression
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(selected_layers))
        self.progress_bar.setValue(0)
        
        # Désactiver le bouton de traitement
        self.process_btn.setEnabled(False)
        
        # Traiter chaque couche
        results_data = {}
        for i, layer in enumerate(selected_layers):
            try:
                result = self.process_single_layer(layer, cd_nom_field, wanted_rank, selected_taxref_fields)
                results_data[layer.name()] = result
            except Exception as e:
                results_data[layer.name()] = f"Erreur - {str(e)}"
                QgsMessageLog.logMessage(f"Erreur sur la couche {layer.name()}: {str(e)}", 
                                       "Speccount", Qgis.Critical)
            
            self.progress_bar.setValue(i + 1)
            
        # Masquer la barre de progression et réactiver le bouton
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        
        # Afficher la fenêtre de récapitulatif
        output_folder = self.folder_widget.filePath() if self.folder_widget.filePath() not in ["Selectionnez un dossier de sortie si besoin", ""] else None
        summary_dialog = ResultsSummaryDialog(results_data, output_folder, self)
        summary_dialog.exec_()
        
    def process_single_layer(self, layer, cd_nom_field, wanted_rank, selected_fields):
        """Traiter une seule couche."""
        # Vérifier que le champ cd_nom existe
        field_names = [field.name() for field in layer.fields()]
        if cd_nom_field not in field_names:
            raise Exception(f"Le champ '{cd_nom_field}' n'existe pas dans la couche")
            
        # Extraire les cd_nom de la couche
        cd_noms = []
        for feature in layer.getFeatures():
            cd_nom = feature[cd_nom_field]
            if cd_nom is not None:
                try:
                    cd_noms.append(int(cd_nom))
                except (ValueError, TypeError):
                    continue
                    
        if not cd_noms:
            raise Exception("Aucun identifiant taxonomique valide trouvé")
            
        obs_df = pd.DataFrame({cd_nom_field: cd_noms})

        # Traitement taxonomique
        # feedback.pushInfo('Traitement taxonomique...')
        obs_ref = get_tri_rang(get_cd_ref_from_cd_nom(obs_df, cd_nom_field, self.taxref_df), self.taxrank_df)
        
        condition_rank = obs_ref['tri_rang'] >= wanted_rank
        nb_imprecis = len(obs_ref[~condition_rank])
        # feedback.pushInfo(f'Nombre d\'observations imprécises : {nb_imprecis} ' + 
        #                  f'({round(100*nb_imprecis/len(obs_ref),2)}%)')

        obs_ref = obs_ref[condition_rank]
        num_obs_to_classify = len(obs_ref)
        # feedback.pushInfo(f'Nombre d\'observations à classer : {num_obs_to_classify}')

        # Comptage par niveau taxonomique
        value_counts = []
        no_matching_rank_num = 0

        while len(obs_ref) > 0:
            no_matching_rank = obs_ref['tri_rang'] < wanted_rank
            no_matching_rank_num += no_matching_rank.sum()
            obs_ref = obs_ref[~no_matching_rank]
            condition_rank = obs_ref['tri_rang'] == wanted_rank
            value_counts.append(obs_ref[condition_rank].value_counts('cd_ref'))
            obs_ref = obs_ref[~condition_rank]
            # feedback.pushInfo(f'Reste {len(obs_ref)} observations à traiter')
            obs_ref = get_tri_rang(get_taxsup(obs_ref, self.taxref_df), self.taxrank_df)
        
        # Création du DataFrame final
        vc_total = reduce(lambda x, y: x.add(y, fill_value=0), value_counts).astype(int)
        final_df = pd.merge(pd.DataFrame(vc_total), 
                          self.taxref_df, 
                          left_index=True, 
                          right_on='cd_nom', 
                          how='left')
        final_df = final_df.rename({0:'count'})

        # Joindre avec taxrank pour obtenir les rangs        
        # Créer la couche de résultats
        output_layer_name = f"{layer.name()}_speccount"
        
        # Définir les champs de sortie
        fields = QgsFields()
        fields.append(QgsField('cd_nom', QMetaType.Int))
        fields.append(QgsField('cd_taxsup', QMetaType.Int))
        fields.append(QgsField('id_rang', QMetaType.QString))

        
        # Ajouter les champs TAXREF sélectionnés
        for field_name in selected_fields:
            if field_name in final_df.columns:
                # Déterminer le type de champ basé sur le contenu
                sample_value = final_df[field_name].dropna().iloc[0] if not final_df[field_name].dropna().empty else ""
                if isinstance(sample_value, (int, float)) and field_name not in ['cd_nom', 'cd_ref', 'cd_taxsup']:
                    field_type = QMetaType.Int if isinstance(sample_value, int) else QMetaType.Double
                else:
                    field_type = QMetaType.QString
                fields.append(QgsField(field_name, field_type))
        
        fields.append(QgsField('count_observations', QMetaType.Int))
        
        # Créer la couche de sortie
        output_layer = QgsVectorLayer("None", output_layer_name, "memory")
        output_layer.dataProvider().addAttributes(fields)
        output_layer.updateFields()
        
        # Compter les observations par espèce
        # Ajouter les features à la couche de sortie
        features = []
        for _, row in final_df.iterrows():
            feature = QgsFeature()
            feature.setFields(fields)
            
            # Remplir les attributs
            feature.setAttribute('cd_nom', int(row['cd_nom']))
            feature.setAttribute('cd_taxsup', int(row['cd_taxsup']))
            feature.setAttribute('id_rang', str(row['id_rang']))

            # Ajouter les champs TAXREF sélectionnés
            for field_name in selected_fields:
                if field_name in final_df.columns:
                    value = row.get(field_name, '')
                    # Convertir les valeurs NaN en chaînes vides
                    if pd.isna(value):
                        value = ''
                    elif isinstance(value, (int, float)) and field_name not in ['cd_nom', 'cd_ref', 'cd_taxsup']:
                        value = int(value) if isinstance(value, float) and value.is_integer() else value
                    else:
                        value = str(value)
                    feature.setAttribute(field_name, value)
            
            feature.setAttribute('count_observations', int(row['count']))
            
            features.append(feature)
            
        output_layer.dataProvider().addFeatures(features)
        
        # Ajouter la couche au projet
        QgsProject.instance().addMapLayer(output_layer)
        
        # Optionnellement sauvegarder dans un fichier
        output_path = None
        if self.folder_widget.filePath() not in ["Selectionnez un dossier de sortie si besoin", ""]:
            output_path = os.path.join(self.folder_widget.filePath(), f"{output_layer_name}.csv")
            
            # TODO : Gérer la déprécation de QgsVectorFileWriter.writeAsVectorFormat utiliser QgsVectorFileWriter.writeAsVectorFormatV3
            error = QgsVectorFileWriter.writeAsVectorFormat(
                output_layer, output_path, "UTF-8", layer.crs(), "CSV"
            )
            if error[0] == QgsVectorFileWriter.NoError:
                QgsMessageLog.logMessage(f"Couche sauvegardée : {output_path}", "Speccount", Qgis.Info)

        return {
            'species_count': len(final_df),
            'imprecis_count': nb_imprecis,
            'no_matching_rank_count': no_matching_rank_num,
            'output_layer_name': output_layer_name,
            'output_path': output_path
        }


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
        from qgis.PyQt.QtWidgets import QAction
        from qgis.PyQt.QtGui import QIcon
        
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