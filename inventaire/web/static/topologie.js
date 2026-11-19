// Affichage du graphe de topologie avec vis-network.
// Les données viennent de l'API /api/topologie (nœuds + liens).

const FORMES = {
  routeur: "diamond",
  commutateur: "square",
  "pare-feu": "triangle",
  segment: "box",
};

const style = getComputedStyle(document.documentElement);
const COULEUR_TEXTE = style.getPropertyValue("--texte").trim() || "#212529";
const COULEUR_LIEN = style.getPropertyValue("--texte-doux").trim() || "#868e96";

let reseau = null;      // instance vis.Network
let donnees = null;     // dernière réponse de l'API

function infobulle(n) {
  if (n.type === "segment") return "Sous-réseau " + n.label;
  return [
    n.label,
    "IP : " + (n.ip || "–"),
    "MAC : " + (n.mac || "–"),
    "Constructeur : " + (n.constructeur || "–"),
    "Type : " + n.type,
    n.en_ligne ? "En ligne" : "Hors ligne",
    n.hors_inventaire ? "(voisin LLDP hors inventaire)" : "",
  ].filter(Boolean).join("\n");
}

// « pc-compta-01.entreprise.lan » → « pc-compta-01 » (graphe plus lisible)
function nomCourt(nom) {
  return /^\d+\.\d+\.\d+\.\d+$/.test(nom) ? nom : nom.split(".")[0];
}

function etiquette(n) {
  if (n.type === "segment") return n.label;
  const nom = nomCourt(n.label);
  return n.ip && n.ip !== nom ? nom + "\n" + n.ip : nom;
}

function versNoeudVis(n) {
  const couleur = COULEURS[n.type] || COULEURS.inconnu;
  return {
    id: n.id,
    label: etiquette(n),
    title: infobulle(n),
    shape: FORMES[n.type] || "dot",
    size: n.type === "routeur" || n.type === "commutateur" ? 22 : 15,
    color: { background: couleur, border: couleur },
    opacity: n.en_ligne ? 1 : 0.35,
    font: { color: n.type === "segment" ? "#212529" : COULEUR_TEXTE, size: 13, multi: false },
    shapeProperties: { borderDashes: n.hors_inventaire ? [4, 4] : false },
  };
}

function versLienVis(l, i) {
  const lldp = l.origine === "lldp";
  return {
    id: i,
    from: l.from,
    to: l.to,
    label: l.label || undefined,
    dashes: !lldp,
    width: lldp ? 2.5 : 1,
    color: { color: COULEUR_LIEN },
    font: { size: 10, color: COULEUR_TEXTE, strokeWidth: 0, align: "middle" },
  };
}

function afficher() {
  const masquer = document.getElementById("masquer-hors-ligne").checked;
  const noeuds = donnees.noeuds.filter(n => !masquer || n.en_ligne);
  const visibles = new Set(noeuds.map(n => n.id));
  const liens = donnees.liens.filter(l => visibles.has(l.from) && visibles.has(l.to));

  const conteneur = document.getElementById("graphe");
  if (noeuds.length === 0) {
    conteneur.innerHTML = '<p class="vide">Aucun équipement à afficher : lancez un scan.</p>';
    return;
  }
  const data = {
    nodes: new vis.DataSet(noeuds.map(versNoeudVis)),
    edges: new vis.DataSet(liens.map(versLienVis)),
  };
  const options = {
    physics: { solver: "forceAtlas2Based", stabilization: { iterations: 300 } },
    interaction: { hover: true, tooltipDelay: 150 },
    edges: { smooth: false },
  };
  if (reseau) reseau.destroy();
  reseau = new vis.Network(conteneur, data, options);

  // Double-clic sur un équipement de l'inventaire : ouverture de sa fiche
  reseau.on("doubleClick", e => {
    const id = e.nodes[0];
    if (id && !id.includes(":")) window.location = URL_FICHE.replace("IP", id);
  });
}

async function charger() {
  donnees = await (await fetch(URL_API)).json();
  afficher();
}

document.getElementById("masquer-hors-ligne").addEventListener("change", afficher);
document.getElementById("recentrer").addEventListener("click", () => reseau && reseau.fit());
charger();
