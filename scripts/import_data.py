import sqlite3
import json
import glob
import os
import re

# tables sans liens (decision, departement, etat, rythme, etudiant)
def decision(cursor): 
    codes_scodoc = [
        # --- codes de Résultat Jury (Classiques) ---
        ("Admis", "ADM"),
        ("Ajourné", "AJ"),
        ("Admis par Compensation", "CMP"),
        ("Admis Supérieur (Décision Jury)", "ADSUP"),
        ("Ajourné (Rattrapage)", "ADJR"),
        ("Ajourné (Jury)", "ADJ"),
        ("Défaillant", "DEF"),
        
        # --- codes de Progression (Passage d'année) ---
        ("Non Admis Redouble", "NAR"),
        ("Redoublement", "RED"),
        ("Passage de Droit", "PASD"),
        ("Passage Conditionnel (AJAC)", "PAS1NCI"), 
        
        # --- codes d'Attente ---
        ("En attente", "ATT"),
        ("En attente (Bloqué)", "ATB"),
        
        # --- codes Spécifiques BUT (Blocs/Compétences) ---
        ("Validé", "V"),
        ("Validé (Variante)", "VAL"),
        ("Non Validé", "NV"),
        ("Validé par Compensation Annuelle", "VCA"),
        ("Validé par Commission", "VCC"),
        ("Admis Sous Réserve", "ADM-INC"),
        
        # --- codes Administratifs/Absences ---
        ("Démissionnaire", "DEM"),
        ("Absence Injustifiée", "ABI"),
        ("Absence Justifiée", "ABJ"),
        ("Excusé", "EXC"),
        ("Non Inscrit", "NI"),

        ("Année Blanche", "ABL"),
        ("Inscrit (En cours)", "INS"),
        ("Abdandon", "ABAN"),
        ("Attente Jury", "ATJ")
        
    ]


    # insertion des données
    cursor.executemany("""
            INSERT OR IGNORE INTO decision (nom, acronyme) 
            VALUES (?, ?)
        """, codes_scodoc)

    print(f"Decisions : {cursor.rowcount} lignes traitées.")

def departement(cursor, data):

    donnees = [ (d['id'] , d['dept_name'], d['acronym']) for d in data ]

    # ajout des deux passerelles qui ne sont pas dans le json formation ni departement 
    donnees.append((9, "Passerelle SD INFO", "P_SD_INFO"))
    donnees.append((10, "Passerelle CJ GEA", "P_CJ_GEA"))

    cursor.executemany("""
            INSERT OR REPLACE INTO departement (id_departement, nom, acronyme)
            VALUES (?, ?, ?)
        """, donnees)
    
    print(f"Departements : {cursor.rowcount} lignes traitées.")

def rythme(cursor):
    cursor.execute("""INSERT OR REPLACE INTO rythme (id_rythme, nom, acronyme) VALUES (1, "Formation Initiale", "FI");""")
    cursor.execute("""INSERT OR REPLACE INTO rythme (id_rythme, nom, acronyme) VALUES (2, "Formation Apprentissage", "FA");""")
    print(f"Rythme : 2 lignes traitées.")

def etat(cursor):
    cursor.execute("""INSERT OR REPLACE INTO etat (id_etat, nom, acronyme) VALUES (1, "Inscrit", "I")""")
    cursor.execute("""INSERT OR REPLACE INTO etat (id_etat, nom, acronyme) VALUES (2, "Démission", "D")""")
    print(f"Etat : 2 lignes lignes traitées.")

def etudiants(cursor, dossier_json):
    # on construit le chemin
    pattern = os.path.join(dossier_json, "decisions_*.json")
    liste_fichiers = glob.glob(pattern)

    if not liste_fichiers:
        print(f"Aucun fichier présent dans: {dossier_json}")
        return

    # on utilise un set pour stocker les INE uniques (déduplication automatique) -> je dit ine mais pour l'instant ine = le hash d'etudid pour pouvoir les suivres à voir avec hébert pour l'après rendu
    ines_uniques = set()
    fichiers_lus = 0

    # lecture de tous les fichiers
    for fichier in liste_fichiers:
        try:
            with open(fichier, 'r', encoding='utf-8') as f:
                contenu = json.load(f)
                
                # on ajoute tous les 'etudid' trouvés dans le set -> il gère les doublons tout seul, paris c'est magique
                for record in contenu:
                    ine = record.get('etudid')
                    if ine:
                        ines_uniques.add(ine)
            
            fichiers_lus += 1

        except json.JSONDecodeError:
            print(f"Erreur JSON dans : {os.path.basename(fichier)}")
        except Exception as e:
            print(f"Erreur lecture {os.path.basename(fichier)} : {e}")


    # on transforme {'id1', 'id2'} en [('id1',), ('id2',)]
    donnees_sql = [(ine,) for ine in ines_uniques]

    # insertion
    cursor.executemany("INSERT OR IGNORE INTO etudiant (ine) VALUES (?)", donnees_sql)
    
    # stats
    nb_ajoutes = cursor.rowcount  # ceux qui ont été réellement insérés
    nb_total_lus = len(ines_uniques) # total d'étudiants distincts trouvés dans les JSON
    nb_deja_presents = nb_total_lus - nb_ajoutes # des maths

    # bilan
    print("\n" + "="*40)
    print(" BILAN ÉTUDIANTS")
    print("="*40)
    print(f"Fichiers traités correctement : {fichiers_lus} / {len(liste_fichiers)}")
    print(f"Étudiants distincts trouvés   : {nb_total_lus}")
    print(f"Nouveaux insérés en base      : {nb_ajoutes}")
    print(f"Déjà connus (ignorés)         : {nb_deja_presents}")
    print("="*40 + "\n")


# tables avec liens (formation, inscription, competences, evaluer, parcours)

def formation(cursor):
    annee_alternance = {
        2: 1,  # GEA  : alternance dès BUT 1
        1: 3,  # CJ   : alternance dès BUT 3
        3: 2,  # GEII : alternance dès BUT 2
        4: 2,  # INFO : alternance dès BUT 2
        5: 2,  # RT   : alternance dès BUT 2
        8: 2   # SD   : alternance dès BUT 2
    }

    ID_FI = 1
    ID_FA = 2

    # on récupère tous les départements
    cursor.execute("SELECT id_departement FROM departement")

    # fetchall renvoie une liste de tuples [(1,), (2,), ...], on l'aplatit en liste simple [1, 2, ...]
    tous_les_departements = [row[0] for row in cursor.fetchall()]

    donnees_a_inserer = []

    # on boucle sur les id existants
    for dept_id in tous_les_departements:
        
        # on skip les passerelles (9 et 10) ici car elles sont des cas particulier qui ont une logique unique (juste l'année 2) qu'on gère plus bas
        if dept_id not in [9, 10]:

            # on peut faire du fi pendant 3 ans pour tt les département
            for annee in [1, 2, 3]:
                donnees_a_inserer.append((annee, dept_id, ID_FI))

            # on peut faire du fa selon les règles plus haut
            if dept_id in annee_alternance:
                debut_fa = annee_alternance[dept_id]
                for annee in [1, 2, 3]:
                    if annee >= debut_fa:
                        donnees_a_inserer.append((annee, dept_id, ID_FA))

    # le cas particulier des passerelles, on vérifie quand même qu'elles sont dans la base pour éviter une erreur SQL
    if 9 in tous_les_departements:
        donnees_a_inserer.append((2, 9, ID_FI))
    
    if 10 in tous_les_departements:
        donnees_a_inserer.append((2, 10, ID_FI))

    # insertion
    cursor.executemany("""
        INSERT OR IGNORE INTO formation (annee_but, id_departement, id_rythme) VALUES (?, ?, ?)
    """, donnees_a_inserer)

    print(f"Formations : {cursor.rowcount} lignes créées (basées sur la table département).")

def get_departement_id(filename, cache_depts):
    """Devine l'ID du département en fonction du nom du fichier"""
    name = filename.lower()
    
    # any() agit comme un 'ou', si au moins un est vrai alors any renvoie true

    # l'ordre à une importance 
    if "passerelle" in name:
        if any(x in name for x in ["sd", "stid", "info", "donn"]):
            return cache_depts.get('P_SD_INFO')
        if any(x in name for x in ["cj", "juridique", "gea"]):
            return cache_depts.get('P_CJ_GEA')
        return None

    if any(x in name for x in ["electrique", "geii"]): return cache_depts.get('GEII')
    if any(x in name for x in ["reseaux", "rt", "r_t"]): return cache_depts.get('RT')
    if any(x in name for x in ["stid", "donn", "_sd_", "but_sd"]): return cache_depts.get('STID')
    if any(x in name for x in ["informatique", "_info_", "but_info"]): return cache_depts.get('INFO')
    if any(x in name for x in ["juridiques", "cj"]): return cache_depts.get('CJ')
    if "gea" in name: return cache_depts.get('GEA')
    return None
def inscription(cursor, dossier_json):
    print("\n" + "="*50)
    print("DÉMARRAGE DES INSCRIPTIONS")
    print("="*50)

    ############################## CACHE ################################################

    # cache pour département pour optimiser la vitesse du code
    cursor.execute("SELECT acronyme, id_departement FROM departement")
    cache_depts = {row[0].upper(): row[1] for row in cursor.fetchall()}
    
    # pareil pour etudiant
    cursor.execute("SELECT ine, id_etudiant FROM etudiant")
    cache_etudiants = {row[0].strip().lower(): row[1] for row in cursor.fetchall()}

    # pareil pour décision
    cursor.execute("SELECT acronyme, id_decision FROM decision")
    cache_decisions = {row[0].upper(): row[1] for row in cursor.fetchall()}

    # pareil pour formation
    cursor.execute("SELECT id_departement, annee_but, id_rythme, id_formation FROM formation")
    cache_formations = {(row[0], row[1], row[2]): row[3] for row in cursor.fetchall()}

    # id des passerelles 
    ID_P_SD_INFO = cache_depts.get('P_SD_INFO')
    ID_P_CJ_GEA = cache_depts.get('P_CJ_GEA')






    ############################## LECTURE DES FICHIERS ################################################

    # on construit le chemin
    pattern = os.path.join(dossier_json, "decisions_*.json") # on prend toutes les décisions de jurys
    fichiers = glob.glob(pattern)
    
    donnees_a_inserer = []
    
    for fichier in fichiers:
        nom_fichier = os.path.basename(fichier)
        
        # on identifie le departement grâce ou nom du fichier
        id_dept = get_departement_id(nom_fichier, cache_depts)
        if not id_dept:
            continue # pour ignorer les fichiers qu'on l'on reconnait pas

        # par défaut on extrait l'année à partir du nom du fichier
        annee_match = re.search(r'(\d{4})', nom_fichier) 
        annee_fichier = int(annee_match.group(1)) if annee_match else None

        nom_lower = nom_fichier.lower()
        mots_cles_alternance = ['fa', 'apprentissage', 'alternance', 'apprenti', 'alt', 'app']
        if any(mot in nom_lower for mot in mots_cles_alternance):
            id_rythme_fichier = 2 # alternant
        else:
            id_rythme_fichier = 1 # initiale

        try:
            with open(fichier, 'r', encoding='utf-8') as f:
                contenu = json.load(f)
        except:
            print(f"Erreur lecture fichier : {nom_fichier}")
            continue

        # protection sur le formatage du JSON, parfois c'est une liste, parfois un dict avec clé 'etudiants'
        liste_etudiants = contenu if isinstance(contenu, list) else contenu.get('etudiants', [])

        for etu in liste_etudiants:
            # identification de l'élève 
            ine = etu.get('etudid') #pour l'instant on dit que etudid est le ine vu qu'on a pas accès au ine
            if not ine: continue
            
            id_etudiant = cache_etudiants.get(str(ine).strip().lower())
            if not id_etudiant: 
                print("esnjhfhesfiuqsdhfidusf") # étudiant inconnu en base, on debug
                continue

            annee_brut = etu.get('annee')
            data_annee = annee_brut if isinstance(annee_brut, dict) else {}

            decision_brut = etu.get('decision')
            data_decision = decision_brut if isinstance(decision_brut, dict) else {}

            semestre_brut = etu.get('semestre')
            data_semestre = semestre_brut if isinstance(semestre_brut, dict) else {}
            





    ############################## EXTRACTION DES DONNEES ################################################
    
            annee_reelle = annee_fichier  # valeur pas défaut
            code_decision = None

            # on cherche dans 'annee' (maintenant data_annee est sûr)
            if not code_decision:
                code_decision = data_annee.get('code')
                
                # on recupere l'année scolaire
                val_annee = data_annee.get('annee_scolaire')
                if val_annee:
                    try:
                        annee_reelle = int(val_annee)
                    except (ValueError, TypeError):
                        pass

            # si rien on cherche dans 'decision'
            if not code_decision:
                code_decision = data_decision.get('code')

            # si encr rien on cherche dans 'semestre' 
            if not code_decision:
                code_decision = data_semestre.get('code')

            # fallback sur l'état administratif
            if not code_decision:
                etat_admin = etu.get('etat')
                if etat_admin == 'D': code_decision = 'DEM'
                elif etat_admin == 'DEF': code_decision = 'DEF'
                elif etat_admin == 'ABAN': code_decision = 'DEM'
                elif etat_admin == 'I': code_decision = 'INS'

            # souvent des semetres pas entièrement compléter avec pas encr des décisions jurys
            if not code_decision:
                # print(f"SKIP: pas de décision pour {ine}") 
                continue 

            if not annee_reelle:
                print(f"SKIP: Pas d'année pour {ine}")
                continue

            id_decision = cache_decisions.get(str(code_decision).upper())
            if not id_decision: 
                continue #décision inconnu mais normalement tte est bon

            # on applique le rythme trouvé grâce au nom du fichier
            id_rythme = id_rythme_fichier

            # son année d'étude
            niveau = 1 # BUT1 par défaut
            val_ordre = str(data_annee.get('ordre', '')).upper()
            if '3' in val_ordre: niveau = 3
            elif '2' in val_ordre: niveau = 2

            # recherche id formation
            cle_cache = (id_dept, niveau, id_rythme)
            id_formation = cache_formations.get(cle_cache)

            # LOGIQUE SPECIALE PASSERELLE : elles sont souvent stockées bizarrement merci scodoc ou hébert, on a pas encr démasqué le coupable
            if id_dept in [ID_P_SD_INFO, ID_P_CJ_GEA]:
                 # si pas trouvé (presque tt le temps) on force le BUT2
                 if not id_formation:
                     id_formation = cache_formations.get((id_dept, 2, id_rythme))

            # sauvetage FA pour les dossiers incomplets, cela permet d'inscrire l'élève même son niveau réel est flou dans le JSON
            if not id_formation and id_rythme == 2:
                    # on tente le niveau 2
                    id_formation = cache_formations.get((id_dept, 2, 2))
                    if not id_formation:
                        # on tente le niveau 3
                        id_formation = cache_formations.get((id_dept, 3, 2))

            if not id_formation: 
                print(f"Formation introuvable pour {ine} (Dept:{id_dept}, Niv:{niveau}, Rythme:{id_rythme})")
                continue

            codes_inactifs = ['DEM', 'DEF', 'ABAN', 'NI', 'D']
            
            if code_decision in codes_inactifs:
                id_etat = 2 # = démission / inactif
            else:
                id_etat = 1 # = inscrit / actif

            # ajout du tuple
            donnees_a_inserer.append(
                (annee_reelle, id_etudiant, id_etat, id_formation, id_decision)
            )





    ############################## INSERTION DES DONNEES ################################################

    print(f"'Préparation de l'insertion de {len(donnees_a_inserer)} inscriptions...")
    
    cursor.executemany("""
        INSERT OR IGNORE INTO inscription 
        (annee_universitaire, id_etudiant, id_etat, id_formation, id_decision) 
        VALUES (?, ?, ?, ?, ?)
    """, donnees_a_inserer)

    print(f"Succès : {cursor.rowcount} inscriptions ajoutées en base.")





# CONFIGURATION DES CHEMINS

# on récupère le dossier où se trouve le script 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# on remonte d'un cran pour avoir la racine du projet
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# on définit les chemins absolus
DB_FILE = os.path.join(PROJECT_ROOT, 'instance', 'scolarite.db')
DOSSIER_JSON = os.path.join(PROJECT_ROOT, 'data', 'json')

# vérif
print(f"Base de données : {DB_FILE}")
print(f"Dossier JSON    : {DOSSIER_JSON}")



# EXECUTION
try:
    # on charge la bd avant la connexion pour éviter de se connecter pour rien
    with open(os.path.join(DOSSIER_JSON, 'departements.json'), 'r', encoding='utf-8') as f:
        departements_json = json.load(f)

    with open(os.path.join(DOSSIER_JSON, 'formations.json'), 'r', encoding='utf-8') as f:
        formation_json = json.load(f)

    # with gère l'ouverture ET la fermeture automatiquement
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        #tables sans clé étrangère
        departement(cursor, departements_json)
        decision(cursor) 
        rythme(cursor)
        etat(cursor)
        etudiants(cursor, DOSSIER_JSON)


        #tables avec clé étrangère
        formation(cursor)
        inscription(cursor, DOSSIER_JSON)

        conn.commit()
        print("carré !")

except FileNotFoundError:
    print("Erreur : Le fichier JSON est introuvable.")
except sqlite3.Error as e:
    print(f"Erreur SQL : {e}")
except Exception as e:
    print(f"Une erreur inattendue est survenue : {e}")