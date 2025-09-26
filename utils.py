"""
Module utilitaire pour le traitement des données taxonomiques de TAXREF.
"""
import pandas as pd

def get_cd_ref_from_cd_nom(obs_df: pd.DataFrame, cd_nom_column: str, taxon_table: pd.DataFrame) -> pd.DataFrame:
    """
    Convertit les cd_nom en cd_ref et enrichit avec les informations taxonomiques.
    
    Args:
        obs_df: DataFrame contenant les observations
        cd_nom_column: Nom de la colonne contenant les cd_nom
        taxon_table: Table TAXREF
    """
    obs_ref = pd.merge(obs_df, taxon_table[['cd_nom', 'cd_ref']], 
                      left_on=cd_nom_column, right_on='cd_nom', 
                      how='left').drop(columns=['cd_nom', cd_nom_column])
    
    obs_ref = pd.merge(obs_ref, taxon_table[['cd_ref', 'cd_nom', 'cd_taxsup','id_rang']], 
                      left_on='cd_ref', right_on='cd_nom', 
                      how='left', suffixes=('','_ref')).drop(columns=['cd_ref_ref'])
    
    assert((obs_ref['cd_ref'] == obs_ref['cd_nom']).all())
    return obs_ref.drop(columns=['cd_nom'])

def get_tri_rang(obs_df: pd.DataFrame, taxrank_table: pd.DataFrame) -> pd.DataFrame:
    """
    Ajoute l'information de tri du rang taxonomique.
    
    Args:
        obs_df: DataFrame avec colonne id_rang
        taxrank_table: Table des rangs taxonomiques
    """
    return obs_df.merge(taxrank_table[['id_rang','tri_rang']], 
                       left_on='id_rang', right_on='id_rang', how='left')

def get_taxsup(obs_df: pd.DataFrame, taxon_table: pd.DataFrame) -> pd.DataFrame:
    """
    Remonte d'un niveau dans la hiérarchie taxonomique.
    
    Args:
        obs_df: DataFrame avec cd_taxsup
        taxon_table: Table TAXREF
    """
    obs_sup = obs_df.merge(taxon_table[['cd_ref', 'cd_nom', 'cd_taxsup', 'id_rang']], 
                          left_on='cd_taxsup', right_on='cd_nom', 
                          how='left', suffixes=('','_sup'))
    
    if 'cd_nom' in obs_df.columns:
        obs_sup = obs_sup[['cd_ref_sup', 'cd_nom_sup','cd_taxsup_sup','id_rang_sup']].rename(
            columns={'cd_ref_sup':'cd_ref',
                    'cd_nom_sup':'cd_nom',
                    'cd_taxsup_sup':'cd_taxsup', 
                    'id_rang_sup':'id_rang'})
    else:
        obs_sup = obs_sup[['cd_ref_sup', 'cd_nom','cd_taxsup_sup','id_rang_sup']].rename(
            columns={'cd_ref_sup':'cd_ref',
                    'cd_taxsup_sup':'cd_taxsup', 
                    'id_rang_sup':'id_rang'})

    return get_cd_ref_from_cd_nom(obs_sup.drop(columns='cd_ref'), 'cd_nom', taxon_table)