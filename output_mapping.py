"""
Module pour la génération de fichiers Excel formatés avec correspondances taxonomiques.

Ce module fournit des fonctions pour :
- Installer automatiquement les dépendances nécessaires
- Merger des données taxonomiques avec TAXREF
- Grouper et formater les données pour l'export Excel
- Appliquer un formatage visuel avec alternance de couleurs

# nb : Module reformatté avec github copilot pour améliorer la lisibilité et la modularité
"""

import pandas as pd
import numpy as np
import subprocess
from qgis.PyQt.QtWidgets import QMessageBox


def install_package(package_name: str) -> None:
    """
    Installe un package Python avec confirmation utilisateur.
    
    Args:
        package_name: Nom du package à installer
    """
    try:
        __import__(package_name)
    except ImportError:
        reply = QMessageBox.question(
            None, 
            "Installation requise",
            f"Le module {package_name} n'est pas installé.\nVoulez-vous l'installer maintenant ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            subprocess.check_call(["pip", "install", package_name])


def merge_with_taxref(df: pd.DataFrame, taxref: pd.DataFrame) -> pd.DataFrame:
    """
    Fusionne les données avec la base TAXREF pour enrichir les informations taxonomiques.
    
    Args:
        df: DataFrame contenant les données à enrichir (avec colonnes 'cd_ref' et 'cd_nom_before')
        taxref: DataFrame TAXREF de référence
        
    Returns:
        DataFrame enrichi avec les informations taxonomiques
    """
    # Première jointure : enrichir cd_ref avec les données TAXREF
    final_df = (df.drop(columns='index')
                .merge(
                    taxref.drop(columns=['cd_ref']), 
                    left_on='cd_ref', 
                    right_on='cd_nom', 
                    how='left'
                )
                .drop(columns='cd_nom'))
    
    # Seconde jointure : enrichir cd_nom_before avec les données TAXREF
    final_df = (final_df
                .merge(
                    taxref[['cd_nom', 'nom_valide', 'nom_vern', 'id_rang']], 
                    left_on='cd_nom_before', 
                    right_on='cd_nom', 
                    how='left', 
                    suffixes=('', '_before')
                )
                .drop(columns='cd_nom'))
    
    return final_df


def group_taxonomic_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Groupe les données taxonomiques par cd_ref et agrège les informations.
    
    Args:
        df: DataFrame avec les données taxonomiques enrichies
        
    Returns:
        DataFrame groupé avec listes de valeurs uniques pour les colonnes '_before'
    """
    # Définir les colonnes à traiter comme listes
    cols_as_list = [
        "cd_nom_before",
        "nom_valide_before", 
        "nom_vern_before",
        "id_rang_before"
    ]
    
    # Identifier les colonnes à garder en première occurrence
    all_cols = df.columns.tolist()
    cols_first = [c for c in all_cols if c not in cols_as_list + ["cd_ref"]]
    
    # Construction du dictionnaire d'agrégation
    agg_dict = {
        **{col: lambda x: list(dict.fromkeys(x)) for col in cols_as_list},
        **{col: "first" for col in cols_first}
    }
    
    # Application du groupby
    result = df.groupby("cd_ref", as_index=False).agg(agg_dict)
    
    return result


def prepare_exploded_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prépare les données pour l'explosion en gérant les listes de tailles différentes.
    
    Args:
        df: DataFrame avec des colonnes contenant des listes
        
    Returns:
        DataFrame avec les listes "explosées" de façon synchronisée
    """
    # Ne traiter que les lignes avec plusieurs correspondances
    df_exploded = df[df['cd_nom_before'].apply(len) > 1].copy()
    
    if df_exploded.empty:
        return df_exploded
    
    # Colonnes à déplier
    cols_to_explode = ["cd_nom_before", "nom_valide_before", "nom_vern_before", "id_rang_before"]
    
    def pad_lists(row):
        """Égalise la longueur de toutes les listes dans une ligne."""
        max_len = max(len(row[col]) for col in cols_to_explode)
        for col in cols_to_explode:
            lst = row[col]
            if len(lst) < max_len:
                lst = lst + [np.nan] * (max_len - len(lst))
            row[col] = lst
        return row
    
    # Égaliser les longueurs des listes
    df_exploded = df_exploded.apply(pad_lists, axis=1)
    
    # Exploser de façon synchronisée
    df_exploded = df_exploded.explode(cols_to_explode)
    
    return df_exploded


def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Réorganise les colonnes en plaçant d'abord les colonnes principales, puis les colonnes '_before'.
    
    Args:
        df: DataFrame à réorganiser
        
    Returns:
        DataFrame avec colonnes réorganisées
    """
    main_cols = [col for col in df.columns if not col.endswith('_before')]
    before_cols = [col for col in df.columns if col.endswith('_before')]
    
    return df[main_cols + before_cols]


def setup_worksheet_formatting(worksheet, workbook, num_index_cols: int, num_data_cols: int) -> tuple:
    """
    Configure le formatage de base de la feuille Excel.
    
    Args:
        worksheet: Feuille Excel xlsxwriter
        workbook: Classeur Excel xlsxwriter  
        num_index_cols: Nombre de colonnes d'index
        num_data_cols: Nombre de colonnes de données
        
    Returns:
        Tuple des formats (format1, format2) pour l'alternance de couleurs
    """
    # Définir les formats de fond alternés
    fmt1 = workbook.add_format({'bg_color': '#F9F9F9'})  # gris clair
    fmt2 = workbook.add_format({'bg_color': '#E0F0FF'})  # bleu très pâle
    
    # Largeur de colonnes automatique
    total_cols = num_index_cols + num_data_cols
    for i in range(total_cols):
        worksheet.set_column(i, i, 25)
    
    # Figer les volets après les colonnes principales
    worksheet.split_panes(0, 8.43 * 20, left_col=25)
    
    return fmt1, fmt2


def apply_alternating_colors(worksheet, df_indexed: pd.DataFrame, fmt1, fmt2) -> None:
    """
    Applique les couleurs alternées par groupe de cd_ref.
    
    Args:
        worksheet: Feuille Excel xlsxwriter
        df_indexed: DataFrame avec index multi-niveaux
        fmt1, fmt2: Formats de couleur alternés
    """
    current_color = fmt1
    last_cd_ref = None
    num_index_cols = len(df_indexed.index.names)
    num_data_cols = len(df_indexed.columns)
    
    # Parcourir les lignes du DataFrame indexé
    for row_idx, (index_tuple, row_data) in enumerate(df_indexed.iterrows(), start=1):
        cd_ref = index_tuple[0]  # Premier niveau de l'index (cd_ref)
        
        # Changer de couleur quand cd_ref change
        if cd_ref != last_cd_ref:
            current_color = fmt2 if current_color == fmt1 else fmt1
            last_cd_ref = cd_ref
        
        # Colorier les colonnes d'index
        for col_idx in range(num_index_cols):
            index_value = index_tuple[col_idx]
            if pd.isna(index_value):
                index_value = ""
            worksheet.write(row_idx, col_idx, index_value, current_color)
        
        # Colorier les colonnes de données
        for col_idx in range(num_data_cols):
            data_col_idx = num_index_cols + col_idx
            cell_value = row_data.iloc[col_idx]
            if pd.isna(cell_value):
                cell_value = ""
            worksheet.write(row_idx, data_col_idx, cell_value, current_color)


def map_output(df: pd.DataFrame, taxref: pd.DataFrame, output_file: str) -> None:
    """
    Génère un fichier Excel formaté avec les correspondances taxonomiques.
    
    Args:
        df: DataFrame contenant les données de correspondance
        taxref: DataFrame TAXREF de référence
        output_file: Chemin du fichier Excel de sortie
    """
    # Vérifier et installer xlsxwriter si nécessaire
    install_package("xlsxwriter")
    
    # 1. Enrichir les données avec TAXREF
    enriched_df = merge_with_taxref(df, taxref)
    
    # 2. Grouper les données par cd_ref
    grouped_df = group_taxonomic_data(enriched_df)
    
    # 3. Préparer les données explosées (pour les correspondances multiples)
    exploded_df = prepare_exploded_data(grouped_df)
    
    # 4. Réorganiser les colonnes
    if not exploded_df.empty:
        reordered_df = reorder_columns(exploded_df)
        
        # 5. Créer l'index multi-niveaux
        main_cols = [col for col in reordered_df.columns if not col.endswith('_before')]
        df_indexed = reordered_df.set_index(main_cols + ['cd_nom_before']).sort_index()
        
        # 6. Générer le fichier Excel avec formatage
        with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
            # Écrire le DataFrame
            df_indexed.to_excel(writer, sheet_name="groupes")
            
            # Récupérer les objets pour le formatage
            workbook = writer.book
            worksheet = writer.sheets["groupes"]
            
            # Configurer le formatage de base
            num_index_cols = len(df_indexed.index.names)
            num_data_cols = len(df_indexed.columns)
            fmt1, fmt2 = setup_worksheet_formatting(worksheet, workbook, num_index_cols, num_data_cols)
            
            # Appliquer les couleurs alternées
            apply_alternating_colors(worksheet, df_indexed, fmt1, fmt2)
