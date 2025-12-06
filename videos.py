import sys
import os
import gurobipy as gp
from gurobipy import GRB

def solve():
    # --- 1. GESTION DES ARGUMENTS ---
    if len(sys.argv) < 2:
        print("Erreur : Il manque le chemin du fichier de données.")
        print("Usage: python videos.py [chemin_vers_le_fichier.in]")
        return

    input_file = sys.argv[1]
    print(f"--- Démarrage du programme ---")
    print(f"Lecture du fichier : {input_file}")

    # --- 2. LECTURE ET PARSING ---
    try:
        with open(input_file, 'r') as f:
            content = f.read().split()
    except FileNotFoundError:
        print(f"Erreur : Le fichier '{input_file}' est introuvable.")
        return

    iterator = iter(content)

    try:
        V = int(next(iterator))
        E = int(next(iterator))
        R = int(next(iterator))
        C = int(next(iterator))
        X = int(next(iterator))

        video_sizes = [int(next(iterator)) for _ in range(V)]

        endpoints = []
        for i in range(E):
            L_d = int(next(iterator)) 
            K = int(next(iterator))   
            connections = {}
            for _ in range(K):
                c_id = int(next(iterator))
                l_c = int(next(iterator))
                connections[c_id] = l_c
            endpoints.append({'L_d': L_d, 'connections': connections})

        requests = []
        for i in range(R):
            Rv = int(next(iterator))
            Re = int(next(iterator))
            Rn = int(next(iterator))
            requests.append({'video': Rv, 'endpoint': Re, 'count': Rn})

    except StopIteration:
        print("Erreur : Le fichier d'entrée est malformé.")
        return

    print(f"Données chargées : {V} vidéos, {E} endpoints, {R} requêtes, {C} caches.")

    # --- 3. PRE-TRAITEMENT ---
    print("Analyse des paires utiles...")
    useful_pairs = set()
    
    # Pour garder en mémoire les gains possibles
    pair_gains = {}

    for req in requests:
        vid = req['video']
        ep_id = req['endpoint']
        count = req['count']
        
        if video_sizes[vid] > X:
            continue
            
        L_d = endpoints[ep_id]['L_d'] 
        
        for c_id, l_c in endpoints[ep_id]['connections'].items():
            if l_c < L_d:
                useful_pairs.add((c_id, vid))
                
                gain = (L_d - l_c) * count
                key = (c_id, vid)
                if key not in pair_gains:
                    pair_gains[key] = 0
                pair_gains[key] += gain

    print(f"Variables 'y' retenues : {len(useful_pairs)}")

    # --- 4. MODELISATION GUROBI ---
    with gp.Env() as env, gp.Model("StreamingVideos", env=env) as model:
        
        # --- PARAMETRES ---
        model.Params.MIPGap = 0.005
        model.Params.LogFile = ""
        
        # Adaptation simple du temps
        if R > 10000:
            print("Gros fichier détecté : on laisse 10 minutes.")
            model.Params.TimeLimit = 600
        else:
            print("Petit fichier : 5 minutes max.")
            model.Params.TimeLimit = 300
        
        # Paramètres pour trouver des solutions rapidement
        model.Params.MIPFocus = 1      # Se concentrer sur la recherche de solutions réalisables
        model.Params.Cuts = 3          # Utiliser beaucoup de coupes pour aider le solveur
        model.Params.Presolve = 2      # Simplifier le modèle avant de résoudre
        model.Params.ProjImpliedCuts = 2 
        
        print("Construction du modèle...")

        # -- Variables --
        y = {}
        for (c, v) in useful_pairs:
            y[c, v] = model.addVar(vtype=GRB.BINARY, name=f"y_{c}_{v}")

        # --- 4b. SOLUTION INITIALE (Glouton) ---
        print("On essaie de trouver une première solution simple...")
        
        candidates_list = []
        for (c, v), total_gain in pair_gains.items():
            density = total_gain / video_sizes[v]
            candidates_list.append({
                'c': c,
                'v': v,
                'density': density,
                'size': video_sizes[v]
            })
            
        # On trie par densité (gain / taille)
        candidates_list.sort(key=lambda x: x['density'], reverse=True)
        
        cache_usage = [0] * C
        count_start = 0
        
        # On remplit les caches avec les meilleures vidéos
        for item in candidates_list:
            c = item['c']
            v = item['v']
            s = item['size']
            
            if cache_usage[c] + s <= X:
                if (c, v) in y:
                    y[c, v].Start = 1.0
                    cache_usage[c] += s
                    count_start += 1
        
        print(f"Solution de départ trouvée avec {count_start} vidéos.")

        # -- Objectif & Contraintes --
        obj_expr = gp.LinExpr()

        for r_idx, req in enumerate(requests):
            vid = req['video']
            ep_id = req['endpoint']
            count = req['count']
            L_d = endpoints[ep_id]['L_d']
            
            possible_x = []

            for c_id, l_c in endpoints[ep_id]['connections'].items():
                if l_c < L_d and (c_id, vid) in y:
                    x_rc = model.addVar(vtype=GRB.BINARY, name=f"x_{r_idx}_{c_id}")
                    model.addConstr(x_rc <= y[c_id, vid])
                    gain = (L_d - l_c) * count
                    obj_expr.add(x_rc, gain)
                    possible_x.append(x_rc)

            if possible_x:
                model.addConstr(gp.quicksum(possible_x) <= 1)

        model.setObjective(obj_expr, GRB.MAXIMIZE)

        print("Ajout contraintes capacité...")
        for c in range(C):
            terms = [video_sizes[v] * y[c, v] for v in range(V) if (c, v) in y]
            if terms:
                model.addConstr(gp.quicksum(terms) <= X, name=f"Capacity_{c}")

        # --- 5. EXPORT ET RESOLUTION ---
        print("Génération MPS...")
        model.write("videos.mps")

        print("Lancement de l'optimisation...")
        model.optimize()

        # --- 6. RESULTATS ---
        if model.SolCount > 0:
            print(f"--- Résultat Final ---")
            print(f"Score (Temps économisé) : {int(model.ObjVal)}")
            print(f"Gap Final : {model.MIPGap * 100:.4f}%")
                
            generate_output_file(y, C, V, "videos.out")
        else:
            print("Aucune solution trouvée.")

def generate_output_file(y_vars, C, V, filename):
    output_lines = []
    
    for c in range(C):
        videos_in_this_cache = []
        for v in range(V):
            if (c, v) in y_vars and y_vars[c, v].X > 0.5:
                videos_in_this_cache.append(str(v))
        
        if videos_in_this_cache:
            line = f"{c} {' '.join(videos_in_this_cache)}"
            output_lines.append(line)

    with open(filename, 'w') as f:
        f.write(f"{len(output_lines)}\n")
        for line in output_lines:
            f.write(line + "\n")
    print(f"Fichier solution écrit : {filename}")

if __name__ == "__main__":
    solve()