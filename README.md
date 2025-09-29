# Plugin QGIS Speccount

Un plugin QGIS pour le comptage d'espèces à partir de la base taxonomique TAXREF.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![QGIS](https://img.shields.io/badge/QGIS-%3E%3D3.0-green.svg)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)

## Description

Le plugin **Speccount** permet de traiter plusieurs couches vectorielles simultanément pour compter les espèces à un rang taxonomique donné en utilisant la base de données TAXREF. Il offre une interface avec sélection multiple des couches et personnalisation des champs de sortie.

### Fonctionnalités principales

- **Traitement multi-couches** : Sélection et traitement simultané de plusieurs couches vectorielles
- **Interface intuitive** : Sélection par cases à cocher avec boutons de raccourci
- **Personnalisation des champs** : Choix des champs TAXREF à inclure dans les résultats
- **Rangs taxonomiques flexibles** : Support de tous les rangs de Règne à Forme
- **Export optionnel** : Sauvegarde des résultats en fichiers CSV
- **Récapitulatif détaillé** : Fenêtre de synthèse avec statistiques globales
- **Gestion des erreurs** : Rapport détaillé des observations imprécises et sans correspondance

## Installation

### Installation depuis le depot de plugins QGIS du Parc National du Mercantour (Recommandé)

- Si le dépôt QGIS du Parc National du Mercantour n'est pas configuré dans QGIS suivre [la procédure d'installation](https://pnmercantour.github.io/donnees/tutos/installation_plugin_via_depot/)
- Dans QGIS allez dans **Extensions** → **Installer/Gérer les extensions**, dans l'onglet **Toutes**, recherchez l'extension Speccount puis cliquez sur **Installer**

### Installation depuis un fichier ZIP

1. Téléchargez le plugin au format ZIP
2. Dans QGIS, allez dans **Extensions** → **Installer/Gérer les extensions**
3. Cliquez sur **Installer depuis un ZIP**
4. Sélectionnez le fichier ZIP du plugin
5. Cliquez sur **Installer l'extension**



## Prérequis

### Dépendances Python
- `pandas`
- `pyarrow` (pour la lecture des fichiers Parquet)

Ces paquets sont actuellement déjà présents dans l'instance python de QGIS.

### Données TAXREF
Le plugin nécessite deux fichiers de données dans le dossier `data/` :
- `taxref.parquet` : Base taxonomique TAXREF -> à mettre à jour régulièrement
- `taxrank.parquet` : Table des rangs taxonomiques

## Utilisation

### Interface principale

1. **Lancement** : Cliquez sur l'icône Speccount dans la barre d'outils ou via le menu Extensions
2. **Sélection des couches** : 
   - Cochez les couches à traiter dans la liste
   - Utilisez les boutons "Tout sélectionner" / "Tout désélectionner"
3. **Configuration des paramètres** :
   - **Champ cd_nom** : Nom du champ contenant les identifiants taxonomiques
   - **Rang taxonomique** : Niveau souhaité (Espèce par défaut)
   - **Dossier de sortie** : Optionnel, pour exporter les résultats en CSV

### Sélection des champs TAXREF

- **Champs par défaut** : `nom_complet`, `nom_vern`
- **Tous les champs** : Sélectionne tous les champs disponibles dans TAXREF
- **Sélection personnalisée** : Cochez uniquement les champs souhaités

### Traitement et résultats

1. Cliquez sur **"Traiter les couches"**
2. Une barre de progression indique l'avancement
3. Une fenêtre de récapitulatif s'affiche avec :
   - Tableau détaillé par couche
   - Statistiques globales
   - Possibilité d'ouvrir le dossier de sortie

## Format des résultats

### Couches de sortie
Chaque couche traitée génère une nouvelle couche `[nom_origine]_speccount` contenant :
- `cd_nom` : Identifiant taxonomique
- `cd_taxsup` : Taxon supérieur
- `id_rang` : Identifiant du rang
- Champs TAXREF sélectionnés
- `count_observations` : Nombre d'observations par espèce

### Fichiers CSV (optionnel)
Exportation des résultats au format CSV avec la même structure.

## Statistiques générées

- **Espèces trouvées** : Nombre d'espèces uniques au rang demandé
- **Observations imprécises** : Taxons de rang insuffisant
- **Sans correspondance** : Identifiants non trouvés dans TAXREF

## Configuration avancée

### Rangs taxonomiques supportés

| Rang | Valeur tri_rang |
|------|----------------|
| Règne (Regnum) | 20 |
| Embranchement (Phylum) | 40 |
| Division | 50 |
| Classe (Classis) | 80 |
| Ordre (Ordo) | 140 |
| Famille (Familia) | 180 |
| Genre (Genus) | 220 |
| Espèce (Species) | 290 |
| Sous-Espèce | 320 |
| Variété | 340 |
| Forme | 360 |

### Champs cd_nom supportés
- `cd_nom` (standard TAXREF)
- `CD_NOM` (majuscules)
- `taxon_id` (alternative)
- `espece_id` (alternative)

## Développement

### Structure du projet
```
speccount_plugin/
├── __init__.py              # Point d'entrée du plugin
├── metadata.txt             # Métadonnées du plugin
├── speccount_multi.py       # Interface principale et logique
├── utils.py                 # Fonctions utilitaires TAXREF
├── icon.png                 # Icône du plugin
└── data/                    # Données TAXREF
    ├── taxref.parquet
    └── taxrank.parquet
```

### Architecture
- **SpecCountMultiDialog** : Interface utilisateur principale
- **ResultsSummaryDialog** : Fenêtre de récapitulatif des résultats
- **SpeccountMultiPlugin** : Gestionnaire du plugin QGIS
- **utils.py** : Fonctions de traitement taxonomique

### Fonctions utilitaires
- `get_cd_ref_from_cd_nom()` : Conversion cd_nom → cd_ref
- `get_tri_rang()` : Ajout des informations de rang
- `get_taxsup()` : Remontée hiérarchique taxonomique

## Historique des versions

### Version 1.0.0
- Interface multi-couches avec sélection par cases à cocher
- Personnalisation des champs TAXREF de sortie
- Fenêtre de récapitulatif avec statistiques détaillées
- Export optionnel en CSV
- Ouverture automatique du dossier de sortie

### TODO
- Mettre au propre le module speccount_multi.py, en particulier séparer la partie interface graphique / retour utilisateur de la partie calculs.
- Eventuellement repenser l'accès et la mise à jour de la base taxref (à l'heure actuelle, le chargement de taxref prend environ 2 secondes)