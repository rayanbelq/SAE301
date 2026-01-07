from flask import Flask, render_template, request, g
import sqlite3
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'scolarite.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row 
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db()
    cursor = conn.cursor()

    # la liste de tout les département sauf les departements qu'on veut pas
    cursor.execute("SELECT acronyme FROM departement WHERE acronyme NOT IN ('FC', 'P_CJ_GEA') ORDER BY acronyme")
    departements = [row['acronyme'] for row in cursor.fetchall()]

    results = []
    # valeurs pas défaut
    selected_dept = "TOUS"
    selected_year = ""
    selected_rythme = "TOUS"

    if request.method == 'POST':
        selected_dept = request.form.get('departement') 
        selected_year = request.form.get('annee')
        selected_rythme = request.form.get('rythme')

        if selected_year:
            try:
                annee_debut = int(selected_year)
                
                # on va construire dynamiquement la requête
                params = [annee_debut]
                
                # partie fixe de la condition WHERE (calcul de l'année)
                sql_conditions = "WHERE i.annee_universitaire = ? + (f.annee_but - 1)"

                # filtre département
                if selected_dept != "TOUS":
                    sql_conditions += " AND d.acronyme = ?"
                    params.append(selected_dept)
                
                # filtre rythme
                if selected_rythme != "TOUS":
                    # on sait que 1=FI et 2=FA dans ta base (tout le temps)
                    if selected_rythme == "FI":
                        sql_conditions += " AND f.id_rythme = 1"
                    elif selected_rythme == "FA":
                        sql_conditions += " AND f.id_rythme = 2"

                query = f"""
                SELECT 
                    e.ine,
                    i.annee_universitaire,
                    f.annee_but,
                    dec.acronyme as resultat,
                    d.acronyme as dept,
                    r.acronyme as rythme
                FROM inscription i
                JOIN formation f ON i.id_formation = f.id_formation
                JOIN departement d ON f.id_departement = d.id_departement
                JOIN etudiant e ON i.id_etudiant = e.id_etudiant
                JOIN rythme r ON f.id_rythme = r.id_rythme  -- Jointure pour afficher le rythme
                LEFT JOIN decision dec ON i.id_decision = dec.id_decision
                {sql_conditions}
                ORDER BY e.ine;
                """
                
                cursor.execute(query, params)
                results = cursor.fetchall()

            except ValueError:
                pass 

    return render_template('index.html', 
                           depts=departements, 
                           results=results, 
                           sel_dept=selected_dept, 
                           sel_year=selected_year,
                           sel_rythme=selected_rythme) # on envoi tte nos données pour les utilisés, logique

if __name__ == '__main__':
    app.run(debug=True)