"""Catalogue complet des sources de données de Lafiya (Pages Web et Guides PDF).

Conformité CDC §6.1 : organisations officielles reconnues (OMS, OMS AFRO, IDF).
Contient 11 pages web officielles et 30 guides cliniques complets en PDF.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceEntry:
    """Définition d'une URL web à scraper."""

    url: str
    source: str
    topic: str
    language: str = "fr"
    content_selector: str = ""
    forced_title: str = ""


@dataclass(frozen=True)
class PdfSourceEntry:
    """Définition d'un guide officiel PDF à télécharger."""

    filename: str
    description: str
    topic: str
    language: str
    handle: str = ""
    direct_url: str = ""


# ------------------------------------------------------------------ Pages Web (11 sources validées)
SOURCES: list[SourceEntry] = [
    # OMS Global
    SourceEntry(
        url="https://www.who.int/fr/news-room/fact-sheets/detail/diabetes",
        source="who",
        topic="diabete",
        content_selector="div.sf-detail-body-wrapper",
        forced_title="Diabète — Aide-mémoire OMS",
    ),
    SourceEntry(
        url="https://www.who.int/fr/news-room/fact-sheets/detail/hypertension",
        source="who",
        topic="hta",
        content_selector="div.sf-detail-body-wrapper",
        forced_title="Hypertension artérielle — Aide-mémoire OMS",
    ),
    SourceEntry(
        url="https://www.who.int/fr/news-room/fact-sheets/detail/obesity-and-overweight",
        source="who",
        topic="general",
        content_selector="div.sf-detail-body-wrapper",
        forced_title="Obésité et surpoids — Aide-mémoire OMS",
    ),
    SourceEntry(
        url="https://www.who.int/fr/news-room/fact-sheets/detail/cardiovascular-diseases-(cvds)",
        source="who",
        topic="hta",
        content_selector="div.sf-detail-body-wrapper",
        forced_title="Maladies cardiovasculaires — Aide-mémoire OMS",
    ),
    # OMS AFRO
    SourceEntry(
        url="https://www.afro.who.int/fr/health-topics/diabetes",
        source="who_afro",
        topic="diabete",
        forced_title="Diabète — OMS Afrique",
    ),
    SourceEntry(
        url="https://www.afro.who.int/fr/health-topics/cardiovascular-diseases",
        source="who_afro",
        topic="hta",
        forced_title="Maladies cardiovasculaires — OMS Afrique",
    ),
    SourceEntry(
        url="https://www.afro.who.int/fr/health-topics/noncommunicable-diseases",
        source="who_afro",
        topic="general",
        forced_title="Maladies non transmissibles — OMS Afrique",
    ),
    # IDF (Fédération Internationale du Diabète)
    SourceEntry(
        url="https://idf.org/about-diabetes/what-is-diabetes/",
        source="idf",
        topic="diabete",
        language="en",
        forced_title="What is diabetes — IDF",
    ),
    SourceEntry(
        url="https://idf.org/about-diabetes/diabetes-complications/",
        source="idf",
        topic="diabete",
        language="en",
        forced_title="Diabetes complications — IDF",
    ),
    SourceEntry(
        url="https://idf.org/about-diabetes/type-2-diabetes/",
        source="idf",
        topic="diabete",
        language="en",
        forced_title="Type 2 diabetes — IDF",
    ),
    SourceEntry(
        url="https://idf.org/about-diabetes/diabetes-prevention/",
        source="idf",
        topic="diabete",
        language="en",
        forced_title="Diabetes prevention — IDF",
    ),
]

# ---------------------------------------------------------------- Guides Officiels PDF (30 guides)
PDF_SOURCES: list[PdfSourceEntry] = [
    # 1. Prise en charge & Diagnostic HTA / MCV (HEARTS & OMS)
    PdfSourceEntry(
        filename="OMS_Lignes_directrices_traitement_hypertension_adulte_2021_FR.pdf",
        description="Lignes directrices OMS pour le traitement pharmacologique de l'hypertension",
        topic="hta",
        language="fr",
        handle="10665/364487",
    ),
    PdfSourceEntry(
        filename="WHO_Guideline_Pharmacological_Treatment_Hypertension_Adults.pdf",
        description="WHO Global Guideline: Pharmacological treatment of hypertension in adults",
        topic="hta",
        language="en",
        handle="10665/344424",
    ),
    PdfSourceEntry(
        filename="OMS_HEARTS_Prise_En_Charge_MCV_Evaluation_Risque.pdf",
        description="HEARTS : Prise en charge des maladies cardiovasculaires fondée sur le risque",
        topic="hta",
        language="fr",
        handle="10665/333221",
    ),
    PdfSourceEntry(
        filename="OMS_HEARTS_Protocoles_Traitement_Donnees_Probantes.pdf",
        description="HEARTS : Protocoles de traitement fondés sur des données probantes",
        topic="hta",
        language="fr",
        handle="10665/260421",
    ),
    PdfSourceEntry(
        filename="OMS_HEARTS_Medicaments_Essentiels_HTA_FR.pdf",
        description="HEARTS : Médicaments essentiels et technologies pour l'hypertension",
        topic="hta",
        language="fr",
        handle="10665/341696",
    ),
    PdfSourceEntry(
        filename="OMS_HEARTS_Acces_Medicaments_Technologies.pdf",
        description="HEARTS : Accès aux médicaments essentiels et technologies de santé",
        topic="hta",
        language="fr",
        handle="10665/260422",
    ),
    PdfSourceEntry(
        filename="OMS_HEARTS_Systemes_Suivi_HTA_FR.pdf",
        description="HEARTS : Systèmes de suivi clinique de l'hypertension",
        topic="hta",
        language="fr",
        handle="10665/327771",
    ),
    PdfSourceEntry(
        filename="OMS_HEARTS_Systemes_Suivi_Clinique.pdf",
        description="HEARTS : Systèmes de suivi clinique pour les soins primaires",
        topic="hta",
        language="fr",
        handle="10665/260423",
    ),
    PdfSourceEntry(
        filename="OMS_HEARTS_Soins_Dispenses_En_Equipe.pdf",
        description="HEARTS : Soins cardiovasculaires dispensés en équipe",
        topic="hta",
        language="fr",
        handle="10665/260424",
    ),
    PdfSourceEntry(
        filename="OMS_HEARTS_Apercu_General_Paquet_Technique.pdf",
        description="HEARTS : Aperçu général du paquet technique de prise en charge",
        topic="hta",
        language="fr",
        handle="10665/329868",
    ),
    # 2. Diabète & Soins de santé primaires
    PdfSourceEntry(
        filename="OMS_Rapport_Mondial_Diabete.pdf",
        description="Rapport mondial de référence sur le diabète de l'OMS",
        topic="diabete",
        language="fr",
        handle="10665/204871",
    ),
    PdfSourceEntry(
        filename="OMS_Module_HEARTS_D_Prise_en_charge_Diabete.pdf",
        description="Module HEARTS-D : Prise en charge du diabète de type 2 en soins primaires",
        topic="diabete",
        language="fr",
        handle="10665/329869",
    ),
    PdfSourceEntry(
        filename="OMS_HEARTS_D_Protocoles_Cliniques_Diabete_FR.pdf",
        description="HEARTS-D : Protocoles cliniques pour le diabète en soins primaires",
        topic="diabete",
        language="fr",
        handle="10665/331710",
    ),
    PdfSourceEntry(
        filename="OMS_Suivi_Mondial_Lutte_Contre_Diabete.pdf",
        description="Orientations OMS sur le suivi mondial pour la lutte contre le diabète",
        topic="diabete",
        language="fr",
        handle="10665/375525",
    ),
    PdfSourceEntry(
        filename="OMS_Indicateurs_Suivi_Diabete_Etablissements_Sante.pdf",
        description="Indicateurs de suivi du diabète dans les établissements de santé",
        topic="diabete",
        language="fr",
        handle="10665/374668",
    ),
    PdfSourceEntry(
        filename="OMS_Cadre_Action_Prevention_Maitrise_Diabete.pdf",
        description="Cadre d'action sur la prévention et la maîtrise du diabète",
        topic="diabete",
        language="fr",
        handle="10665/348633",
    ),
    # 3. Nutrition, Sel & Lipides
    PdfSourceEntry(
        filename="OMS_Lignes_directrices_Apport_Sodium_Sel_FR.pdf",
        description="Lignes directrices OMS : Apport en sodium (sel) chez l'adulte et l'enfant",
        topic="hta",
        language="fr",
        handle="10665/85224",
    ),
    PdfSourceEntry(
        filename="OMS_Lignes_Directrices_Substituts_Sel_Faible_Sodium.pdf",
        description="Lignes directrices OMS : Substituts du sel à faible teneur en sodium",
        topic="hta",
        language="fr",
        handle="10665/375782",
    ),
    PdfSourceEntry(
        filename="OMS_Lignes_Directrices_Apport_Graisses_Totales_Prevention_Poids.pdf",
        description="Lignes directrices : Apport en graisses et prévention de la prise de poids",
        topic="general",
        language="fr",
        handle="10665/341135",
    ),
    # 4. Activité physique & Sédentarité
    PdfSourceEntry(
        filename="OMS_Lignes_directrices_Activite_Physique_Sedentarite_FR.pdf",
        description="Lignes directrices OMS : activité physique et comportements sédentaires",
        topic="general",
        language="fr",
        handle="10665/337001",
    ),
    PdfSourceEntry(
        filename="OMS_Lignes_Directrices_Activite_Physique_Coup_Oeil.pdf",
        description="Lignes directrices OMS sur l'activité physique : en un coup d'œil",
        topic="general",
        language="fr",
        handle="10665/337003",
    ),
    PdfSourceEntry(
        filename="OMS_Promouvoir_Activite_Physique_Soins_Sante_Primaires.pdf",
        description="Promouvoir l'activité physique dans les soins de santé primaires",
        topic="general",
        language="fr",
        handle="10665/351348",
    ),
    # 5. Obésité & Surpoids
    PdfSourceEntry(
        filename="OMS_Rapport_Technique_Prevention_Prise_En_Charge_Obesite.pdf",
        description="Rapport technique OMS : Prévention et prise en charge de l'obésité",
        topic="general",
        language="fr",
        handle="10665/42330",
    ),
    PdfSourceEntry(
        filename="OMS_Rapport_Commission_Mettre_Fin_Obesite_Enfant.pdf",
        description="Rapport de la Commission pour mettre fin à l'obésité de l'enfant",
        topic="general",
        language="fr",
        handle="10665/204176",
    ),
    PdfSourceEntry(
        filename="OMS_Approches_Prevention_Obesite_Population.pdf",
        description="Approches de la prévention de l'obésité dans la population",
        topic="general",
        language="fr",
        handle="10665/75153",
    ),
    # 6. Spécificités Afrique & Soins primaires en ressources limitées
    PdfSourceEntry(
        filename="OMS_AFRO_Maladies_Cardiovasculaires_Region_Africaine.pdf",
        description="Les maladies cardiovasculaires dans la Région africaine (Comité OMS AFRO)",
        topic="hta",
        language="fr",
        handle="10665/119934",
    ),
    PdfSourceEntry(
        filename="OMS_AFRO_Evaluation_Prise_En_Charge_Hypertension_FR.pdf",
        description="Prise en charge et impact de l'hypertension en Afrique (OMS AFRO)",
        topic="hta",
        language="fr",
        handle="10665/340308",
    ),
    PdfSourceEntry(
        filename="OMS_Bulletin_Hypertension_Arterielle_Afrique.pdf",
        description="L'hypertension artérielle en Afrique (Bulletin officiel OMS)",
        topic="hta",
        language="fr",
        handle="10665/254425",
    ),
    PdfSourceEntry(
        filename="WHO_PEN_Interventions_Essentielles_Soins_Primaires.pdf",
        description="WHO PEN : Interventions essentielles MNT pour les soins primaires",
        topic="general",
        language="en",
        handle="10665/334181",
    ),
    PdfSourceEntry(
        filename="OMS_Suivi_Maladies_Non_Transmissibles_Etablissements_Sante.pdf",
        description="Suivi des maladies non transmissibles dans les centres de santé",
        topic="general",
        language="fr",
        handle="10665/358814",
    ),
]
