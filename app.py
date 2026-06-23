import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="ITM - Assistant FL Pro", page_icon="🍏", layout="centered")


# --- INITIALISATION INTELLIGENTE DU CATALOGUE ---
if 'catalogue_fl' not in st.session_state:
    try:
       # 1. On lit le fichier brut en texte pour ne rien perdre
        df_temp = pd.read_csv("cadencier.csv", sep=";", dtype=str)
        
        # Si jamais Excel a utilisé des virgules, on bascule dessus
        if "PLU" not in df_temp.columns and "PLU " not in df_temp.columns:
            df_temp = pd.read_csv("cadencier.csv", sep=",", dtype=str)
        
        # 2. NETTOYAGE : On enlève les espaces (comme dans "PLU ") et on met tout en MAJUSCULES
        df_temp.columns = df_temp.columns.str.strip().str.upper()
        
        # On définit le PLU nettoyé comme index
        df_temp = df_temp.set_index("PLU")
        
        # 3. TRADUCTION : On renomme tes colonnes majuscules vers le format attendu par le code
        mapping_colonnes = {
            "PRODUIT": "Produit",
            "UNITE": "Unite",
            "STOCK_INITIAL": "Stock_Initial",
            "PA_BRUT": "PA_Brut",
            "TVA": "TVA",
            "MARGE": "Marge",
            "PV_NET": "PV_Net",
            "COLISAGE": "Colisage",
            "STOCK_SECURITE": "Stock_Securite",
            "VENTE_SEMAINE": "Vente_Semaine",
            "VENTE_SAMEDI": "Vente_Samedi",
            "VENTE_DIMANCHE": "Vente_Dimanche",
            "VENTE_J": "Ventes_J",   # Corrige le "S" manquant
            "VENTES_J": "Ventes_J",
            "CASSE_J": "Casse_J",
            "LIVRE_CE_MATIN": "Livre_Ce_Matin"
        }
        df_temp = df_temp.rename(columns=mapping_colonnes)
        
        # 4. CONVERSION : On transforme les textes en vrais chiffres et on gère les virgules françaises (ex: 1,80 -> 1.80)
        num_cols = ["Stock_Initial", "PA_Brut", "TVA", "Marge", "PV_Net", "Colisage", "Stock_Securite", "Vente_Semaine", "Vente_Samedi", "Vente_Dimanche", "Ventes_J", "Casse_J", "Livre_Ce_Matin"]
        for col in num_cols:
            if col in df_temp.columns:
                df_temp[col] = df_temp[col].astype(str).str.replace(",", ".")
                df_temp[col] = pd.to_numeric(df_temp[col], errors='coerce').fillna(0)
        
        # On stocke le résultat propre dans l'application
        st.session_state.catalogue_fl = df_temp
        
    except Exception as e:
       st.error(f"⚠️ Erreur lors du chargement du cadencier : {e}")
        st.stop()

df = st.session_state.catalogue_fl

st.title("🍏 Mon Assistant FL")
st.caption("Outil d'aide à la commande journalière — Intermarché")

tabs = st.tabs(["📅 Contexte Jour", "📸 Saisies & Scans", "📦 Mon Rayon", "🛒 Cadencier Commande"])

# --- TAB 1 : CONTEXTE DU JOUR ---
with tabs[0]:
    st.header("📅 Configuration du jour")
    jour_commande = st.selectbox("Quel jour passe-tu la commande ?", ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"])
    
    if jour_commande == "Vendredi":
        st.warning("⚠️ Mode Week-end Activé : La commande couvrira Samedi + Dimanche.")
        c1, c2 = st.columns(2)
        with c1: m_sam = st.selectbox("Météo Samedi", ["Normal", "Pluie/Froid", "Grand Soleil"])
        with c2: m_dim = st.selectbox("Météo Dimanche", ["Normal", "Pluie/Froid", "Grand Soleil"])
        coeffs = {"Normal": 1.0, "Pluie/Froid": 0.8, "Grand Soleil": 1.3}
        cm1, cm2 = coeffs[m_sam], coeffs[m_dim]
    else:
        m_demain = st.selectbox("Météo Demain", ["Normal", "Pluie/Froid", "Grand Soleil"])
        coeffs = {"Normal": 1.0, "Pluie/Froid": 0.8, "Grand Soleil": 1.3}
        cm1, cm2 = coeffs[m_demain], 0

# --- TAB 2 : SAISIES TERRAIN ---
with tabs[1]:
    st.header("📸 Entrées & Sorties (Scans et Saisies)")
    
    for plu in df.index:
        with st.expander(f"⚙️ {df.loc[plu, 'Produit']} (PLU: {plu})"):
            df.loc[plu, "Livre_Ce_Matin"] = st.number_input("Reçu ce matin (BL)", min_value=0, value=int(df.loc[plu, "Livre_Ce_Matin"]), key=f"l_{plu}")
            df.loc[plu, "Ventes_J"] = st.number_input("Ventes estimées du jour", min_value=0, value=int(df.loc[plu, "Ventes_J"]), key=f"v_{plu}")
            # ICI : Correction du 'l' par 'plu' à la fin de la ligne
            df.loc[plu, "Casse_J"] = st.number_input("Casse constatée (Feuille de démarque)", min_value=0, value=int(df.loc[plu, "Casse_J"]), key=f"c_{plu}")
# --- TAB 3 : LE RAYON ---
with tabs[2]:
    st.header("📦 État du Rayon & Marges")
    
    # Simulation d'un scan d'étiquette électronique
    scan = st.text_input("🔍 Flasher une étiquette électronique (Saisir le PLU) :")
    if scan in df.index:
        st.info(f"Produit détecté : {df.loc[scan, 'Produit']}")
        nouveau_s = st.number_input("Corriger le stock réel en rayon :", value=int(df.loc[scan, "Stock_Initial"]))
        df.loc[scan, "Stock_Initial"] = nouveau_s
    
    st.write("---")
    st.dataframe(df[["Produit", "Colisage", "Stock_Securite", "PV_Net"]])

# --- TAB 4 : CALCUL DE LA COMMANDE ---
with tabs[3]:
    st.header("🛒 Proposition de Commande")
    propositions = []
    
    for plu in df.index:
        stock_soir = max(0, (df.loc[plu, "Stock_Initial"] + df.loc[plu, "Livre_Ce_Matin"]) - df.loc[plu, "Ventes_J"] - df.loc[plu, "Casse_J"])
        
        if jour_commande == "Vendredi":
            besoin_vente = (df.loc[plu, "Vente_Samedi"] * cm1) + (df.loc[plu, "Vente_Dimanche"] * cm2)
        else:
            besoin_vente = df.loc[plu, "Vente_Semaine"] * cm1
            
        besoin_brut = max(0, besoin_vente + df.loc[plu, "Stock_Securite"] - stock_soir)
        nb_colis = math.ceil(besoin_brut / df.loc[plu, "Colisage"])
        
        propositions.append({
            "Article": df.loc[plu, "Produit"],
            "Stock Est. Ce Soir": f"{stock_soir} {df.loc[plu, 'Unite']}",
            "Besoin Réel": f"{round(besoin_brut, 1)} {df.loc[plu, 'Unite']}",
            "A COMMANDER": f"🔴 {nb_colis} COLIS" if nb_colis > 0 else "❌ Stock OK"
        })
        
    st.table(pd.DataFrame(propositions).set_index("Article"))
