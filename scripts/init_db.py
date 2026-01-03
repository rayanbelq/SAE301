import sqlite3
import os

def create_database(db_name="scolarite.db"):
    # supprimer l'ancien fichier s'il existe pour repartir de zéro, comment ça facilite la vie wow
    if os.path.exists(db_name):
        os.remove(db_name)

    try:
        # connexion à la base de données (elle sera créée si elle n'existe pas)
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        # activer le support des clés étrangères
        cursor.execute("PRAGMA foreign_keys = ON;")


        # tables indépendantes (sans clés étrangères)
        cursor.execute("""
        CREATE TABLE decision(
            id_decision INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            acronyme TEXT NOT NULL UNIQUE
        );
        """)

        cursor.execute("""
        CREATE TABLE etat(
            id_etat INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            acronyme TEXT NOT NULL UNIQUE
        );
        """)

        cursor.execute("""
        CREATE TABLE rythme(
            id_rythme INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            acronyme TEXT NOT NULL UNIQUE
        );
        """)

        cursor.execute("""
        CREATE TABLE departement(
            id_departement INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            acronyme TEXT NOT NULL UNIQUE
        );
        """)

        cursor.execute("""
        CREATE TABLE etudiant(
            id_etudiant INTEGER PRIMARY KEY AUTOINCREMENT,
            ine TEXT NOT NULL UNIQUE
        );
        """)

        # tables dépendantes

        cursor.execute("""
        CREATE TABLE formation(
            id_formation INTEGER PRIMARY KEY AUTOINCREMENT,
            annee_but INTEGER NOT NULL,
            id_departement INTEGER NOT NULL,
            id_rythme INTEGER NOT NULL,
            FOREIGN KEY(id_departement) REFERENCES departement(id_departement),
            FOREIGN KEY(id_rythme) REFERENCES rythme(id_rythme)

            -- la magie
            UNIQUE(annee_but, id_departement, id_rythme)
        );
        """)

        cursor.execute("""
        CREATE TABLE parcours(
            id_parcours INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(10) NOT NULL,
            nom VARCHAR(255) NOT NULL,
            id_departement INT NOT NULL,
            FOREIGN KEY(id_departement ) REFERENCES departement(id_departement )
            );
        """)

        cursor.execute("""
        CREATE TABLE competence(
            id_competence INTEGER PRIMARY KEY AUTOINCREMENT,
            nom VARCHAR(255) NOT NULL,
            acronyme VARCHAR(10) NOT NULL,
            id_parcours  INT NOT NULL,
            FOREIGN KEY(id_parcours) REFERENCES parcours(id_parcours)
        );
        """)

        cursor.execute("""
        CREATE TABLE inscription(
            id_inscription INTEGER PRIMARY KEY AUTOINCREMENT,
            annee_universitaire INTEGER NOT NULL,
            id_etudiant INTEGER NOT NULL,
            id_etat INTEGER NOT NULL,
            id_formation INTEGER NOT NULL,
            id_decision INTEGER,
            FOREIGN KEY(id_decision) REFERENCES decision(id_decision),
            FOREIGN KEY(id_etudiant) REFERENCES etudiant(id_etudiant),
            FOREIGN KEY(id_etat) REFERENCES etat(id_etat),
            FOREIGN KEY(id_formation) REFERENCES formation(id_formation),
            UNIQUE(id_etudiant, annee_universitaire)
        );
        """)

        cursor.execute("""
        CREATE TABLE evaluer(
            id_inscription INTEGER,
            id_competence INTEGER,
            id_decision INTEGER,
            moyenne DECIMAL(4,2), 
            PRIMARY KEY(id_inscription, id_competence),
            FOREIGN KEY(id_inscription) REFERENCES inscription(id_inscription),
            FOREIGN KEY(id_competence) REFERENCES competence(id_competence),
            FOREIGN KEY(id_decision) REFERENCES decision(id_decision)
        );
        """)

        # on valide
        conn.commit()
        
        # vérif rapide : lister les tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("\nListe des tables dans la base :")
        for table in tables:
            print(f"- {table[0]}")

    except sqlite3.Error as e:
        print(f"Une erreur est survenue : {e}")
        
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_database()