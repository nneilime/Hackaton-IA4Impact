// Lieux à découvrir près des gares — données de démonstration (mock), pas encore servies par l'API.
// Chaque lieu est rattaché à une gare par son identifiant (backend/data/stations_occitanie.csv) ; la distance à
// pied est calculée à partir des coordonnées, pas écrite à la main. Photos : public/discoveries/<id>.jpg,
// téléchargées depuis Wikimedia Commons par scripts/fetch-discoveries.py, crédits dans discovery-credits.json.
import credits from "./discovery-credits.json";
import modelCredits from "./model-credits.json";

export type Text = { en: string; fr: string };
export type Category = "heritage" | "museum" | "nature" | "engineering" | "music" | "sport" | "science" | "craft";
export const CATEGORIES: Category[] = ["heritage", "museum", "nature", "engineering", "music", "sport", "science", "craft"];

export type Discovery = {
  id: string;
  stationId: string;
  category: Category;
  lat: number;
  lon: number;
  title: Text;
  era: Text; // époque, affichée en étiquette
  summary: Text; // une phrase, sur la vignette
  description: Text[]; // paragraphes de la fiche
  didYouKnow: Text;
};

export type Credit = { author: string; license: string; source: string };

export const imageOf = (d: Discovery) => `${import.meta.env.BASE_URL}discoveries/${d.id}.jpg`;
export const creditOf = (d: Discovery): Credit | undefined => (credits as Record<string, Credit>)[d.id];

// Modèle 3D du bâtiment, quand il en existe un : public/models/<id>.glb, récupéré sur Sketchfab puis allégé
// (décimation Blender + gltf-transform, textures WebP 1024, compression meshopt). Crédits dans model-credits.json.
export const modelCreditOf = (d: Discovery): Credit | undefined => (modelCredits as Record<string, Credit>)[d.id];
export const modelOf = (d: Discovery) => (modelCreditOf(d) ? `${import.meta.env.BASE_URL}models/${d.id}.glb` : undefined);

export const DISCOVERIES: Discovery[] = [
  // ── Toulouse Matabiau ──────────────────────────────────
  {
    id: "canal-du-midi",
    stationId: "87611004",
    category: "engineering",
    lat: 43.6103,
    lon: 1.4527,
    title: { en: "Canal du Midi", fr: "Canal du Midi" },
    era: { en: "1666 – 1681", fr: "1666 – 1681" },
    summary: {
      en: "A 17th-century waterway linking the Atlantic to the Mediterranean, right across from the station.",
      fr: "La voie d'eau du XVIIᵉ siècle qui relie l'Atlantique à la Méditerranée, juste en face de la gare.",
    },
    description: [
      {
        en: "Designed by Pierre-Paul Riquet, the canal runs about 240 km from Toulouse to the Étang de Thau. Combined with the Garonne, it gave boats a route between the two seas without sailing around Spain.",
        fr: "Imaginé par Pierre-Paul Riquet, le canal court sur environ 240 km de Toulouse à l'étang de Thau. Relié à la Garonne, il offrait aux bateaux un passage entre les deux mers sans contourner l'Espagne.",
      },
      {
        en: "Its hardest problem was water: Riquet collected streams from the Montagne Noire into a reservoir and fed them to the canal's highest point, the Seuil de Naurouze. It has been a UNESCO World Heritage Site since 1996.",
        fr: "Le vrai défi était l'eau : Riquet a capté les ruisseaux de la Montagne Noire dans un réservoir pour alimenter le point le plus haut du canal, le seuil de Naurouze. Il est inscrit au patrimoine mondial de l'UNESCO depuis 1996.",
      },
    ],
    didYouKnow: {
      en: "Riquet financed much of the work himself and died in 1680, a few months before the canal opened.",
      fr: "Riquet a financé une grande partie des travaux lui-même et est mort en 1680, quelques mois avant l'ouverture du canal.",
    },
  },
  {
    id: "saint-sernin",
    stationId: "87611004",
    category: "heritage",
    lat: 43.6085,
    lon: 1.4421,
    title: { en: "Basilica of Saint-Sernin", fr: "Basilique Saint-Sernin" },
    era: { en: "11th – 12th century", fr: "XIᵉ – XIIᵉ siècle" },
    summary: {
      en: "One of the largest Romanesque churches in Europe, built for pilgrims on the way to Santiago.",
      fr: "L'une des plus grandes églises romanes d'Europe, bâtie pour les pèlerins de Compostelle.",
    },
    description: [
      {
        en: "The basilica stands over the tomb of Saturnin, the first bishop of Toulouse. Its size was meant for crowds: pilgrims could walk around the choir through the ambulatory to see the relics without disturbing the services.",
        fr: "La basilique s'élève sur le tombeau de Saturnin, premier évêque de Toulouse. Sa taille répondait à l'afflux : les pèlerins faisaient le tour du chœur par le déambulatoire pour voir les reliques sans gêner les offices.",
      },
      {
        en: "Look at the octagonal bell tower: the lower floors have round Romanesque arches, the upper ones pointed mitre arches added later. It is part of the UNESCO listing of the Routes of Santiago de Compostela.",
        fr: "Regardez le clocher octogonal : les étages du bas ont des arcs romans en plein cintre, ceux du haut des arcs en mitre ajoutés plus tard. Elle fait partie des Chemins de Compostelle inscrits à l'UNESCO.",
      },
    ],
    didYouKnow: {
      en: "Saturnin, \"Sernin\" in Occitan, was martyred by being tied to a bull — the street Rue du Taur (\"bull\") still remembers it.",
      fr: "Saturnin, « Sernin » en occitan, fut martyrisé attaché à un taureau — la rue du Taur en garde le souvenir.",
    },
  },
  {
    id: "capitole",
    stationId: "87611004",
    category: "heritage",
    lat: 43.6044,
    lon: 1.444,
    title: { en: "Le Capitole", fr: "Le Capitole" },
    era: { en: "18th-century façade", fr: "Façade du XVIIIᵉ siècle" },
    summary: {
      en: "Toulouse's city hall and opera house, facing the city's great square.",
      fr: "L'hôtel de ville et l'opéra de Toulouse, face à la grande place de la ville.",
    },
    description: [
      {
        en: "The name comes from the capitouls, the magistrates who governed Toulouse from the Middle Ages to the Revolution. The pink-brick and stone façade, 135 m long, was built in the 1750s.",
        fr: "Le nom vient des capitouls, les magistrats qui gouvernaient Toulouse du Moyen Âge à la Révolution. La façade de brique rose et de pierre, longue de 135 m, date des années 1750.",
      },
      {
        en: "On the square, a large Occitan cross with the signs of the zodiac is set into the paving. Inside, the Salle des Illustres is open to visitors when no ceremony is held.",
        fr: "Sur la place, une grande croix occitane ornée des signes du zodiaque est incrustée dans le pavé. À l'intérieur, la salle des Illustres se visite quand aucune cérémonie n'a lieu.",
      },
    ],
    didYouKnow: {
      en: "The eight pink marble columns on the façade stand for the eight original capitouls.",
      fr: "Les huit colonnes de marbre rose de la façade représentent les huit capitouls d'origine.",
    },
  },

  // ── Carcassonne ────────────────────────────────────────
  {
    id: "cite-carcassonne",
    stationId: "87615286",
    category: "heritage",
    lat: 43.2067,
    lon: 2.3636,
    title: { en: "La Cité de Carcassonne", fr: "La Cité de Carcassonne" },
    era: { en: "Antiquity – 13th century", fr: "Antiquité – XIIIᵉ siècle" },
    summary: {
      en: "A medieval fortified town with two rings of walls, restored in the 19th century.",
      fr: "Une ville fortifiée médiévale à double enceinte, restaurée au XIXᵉ siècle.",
    },
    description: [
      {
        en: "The hill has been fortified since Roman times. The double ring of walls — about 3 km long with 52 towers — mostly dates from the 13th century, when the kings of France turned it into a border fortress facing Aragon.",
        fr: "La colline est fortifiée depuis l'époque romaine. La double enceinte — environ 3 km et 52 tours — date surtout du XIIIᵉ siècle, quand les rois de France en ont fait une forteresse face à l'Aragon.",
      },
      {
        en: "Falling into ruin, it was saved from demolition and restored from 1853 by the architect Viollet-le-Duc. His slate-roofed towers are still debated, since roofs in the south were usually tiled. UNESCO World Heritage since 1997.",
        fr: "Tombée en ruine, elle échappe à la démolition et est restaurée à partir de 1853 par l'architecte Viollet-le-Duc. Ses toits d'ardoise font encore débat : dans le Midi, on couvrait plutôt de tuiles. Patrimoine mondial de l'UNESCO depuis 1997.",
      },
    ],
    didYouKnow: {
      en: "Legend says Dame Carcas ended a five-year siege by throwing a pig stuffed with grain over the walls, to show the city still had food to spare.",
      fr: "La légende veut que Dame Carcas ait mis fin à un siège de cinq ans en jetant par-dessus les remparts un cochon gavé de blé, pour faire croire que la ville ne manquait de rien.",
    },
  },

  // ── Nîmes ──────────────────────────────────────────────
  {
    id: "arenes-nimes",
    stationId: "87775007",
    category: "heritage",
    lat: 43.8349,
    lon: 4.3596,
    title: { en: "Arena of Nîmes", fr: "Arènes de Nîmes" },
    era: { en: "Late 1st century AD", fr: "Fin du Iᵉʳ siècle apr. J.-C." },
    summary: {
      en: "One of the best-preserved Roman amphitheatres in the world, still used for shows.",
      fr: "L'un des amphithéâtres romains les mieux conservés au monde, toujours utilisé pour des spectacles.",
    },
    description: [
      {
        en: "About 133 m long and 101 m wide, the arena could seat some 24,000 spectators who came to watch gladiator fights and animal hunts. Its 34 rows of seats were assigned by social rank: the closer to the ring, the more important.",
        fr: "Longue d'environ 133 m et large de 101 m, l'arène accueillait quelque 24 000 spectateurs venus voir combats de gladiateurs et chasses aux fauves. Ses 34 rangées de gradins étaient attribuées selon le rang social : plus on était proche de la piste, plus on était important.",
      },
      {
        en: "In the Middle Ages it became a fortress, then a whole neighbourhood with houses and a chapel built inside. Those were cleared in the 19th century to reveal the monument.",
        fr: "Au Moyen Âge, elle devient une forteresse, puis un véritable quartier avec ses maisons et sa chapelle bâties à l'intérieur. Ils ont été dégagés au XIXᵉ siècle pour rendre le monument visible.",
      },
    ],
    didYouKnow: {
      en: "The Romans could stretch a huge canvas awning, the velum, over the spectators — the stones that held its masts are still visible at the top.",
      fr: "Les Romains pouvaient tendre une immense toile, le velum, au-dessus des spectateurs — les pierres qui tenaient ses mâts se voient encore au sommet.",
    },
  },
  {
    id: "maison-carree",
    stationId: "87775007",
    category: "heritage",
    lat: 43.8382,
    lon: 4.3561,
    title: { en: "Maison Carrée", fr: "Maison Carrée" },
    era: { en: "Around 5 AD", fr: "Vers l'an 5 apr. J.-C." },
    summary: {
      en: "A Roman temple so intact it still has its roof — UNESCO World Heritage since 2023.",
      fr: "Un temple romain si intact qu'il a encore son toit — patrimoine mondial de l'UNESCO depuis 2023.",
    },
    description: [
      {
        en: "Despite its name (\"square house\"), it is a rectangle. The temple was dedicated to Gaius and Lucius Caesar, the grandsons of Emperor Augustus, and stood at the edge of the forum of Nemausus.",
        fr: "Malgré son nom, c'est un rectangle. Le temple était dédié à Caius et Lucius César, les petits-fils de l'empereur Auguste, et bordait le forum de Nemausus.",
      },
      {
        en: "It survived because it was always in use: town hall, house, stable, church, archive and museum. Across the square, the Carré d'Art by Norman Foster echoes it in glass and steel.",
        fr: "Il a survécu parce qu'il a toujours servi : maison consulaire, habitation, écurie, église, archives puis musée. En face, le Carré d'Art de Norman Foster lui répond en verre et en acier.",
      },
    ],
    didYouKnow: {
      en: "Thomas Jefferson admired it so much that he used it as the model for the Virginia State Capitol in Richmond.",
      fr: "Thomas Jefferson l'admirait tant qu'il en a fait le modèle du Capitole de l'État de Virginie, à Richmond.",
    },
  },
  {
    id: "jardins-fontaine",
    stationId: "87775007",
    category: "nature",
    lat: 43.8385,
    lon: 4.3499,
    title: { en: "Jardins de la Fontaine", fr: "Jardins de la Fontaine" },
    era: { en: "18th century, on a Roman site", fr: "XVIIIᵉ siècle, sur un site romain" },
    summary: {
      en: "One of the first public gardens in Europe, built around the spring that founded the city.",
      fr: "L'un des premiers jardins publics d'Europe, construit autour de la source qui a fondé la ville.",
    },
    description: [
      {
        en: "Nîmes was born at this spring, sacred to the Celtic god Nemausus who gave the city its name. In the 1740s, engineers built terraces, basins and balustrades around it, creating a French-style garden open to all.",
        fr: "Nîmes est née de cette source, consacrée au dieu celte Nemausus qui a donné son nom à la ville. Dans les années 1740, des ingénieurs l'entourent de terrasses, de bassins et de balustrades : un jardin à la française ouvert à tous.",
      },
      {
        en: "Inside the garden lie the ruins of the so-called Temple of Diana, and at the top of the hill stands the Tour Magne, a Roman tower with a view over the whole city.",
        fr: "Dans le jardin se trouvent les vestiges du « temple de Diane », et au sommet de la colline se dresse la tour Magne, une tour romaine d'où l'on voit toute la ville.",
      },
    ],
    didYouKnow: {
      en: "The Tour Magne was dug into in the 17th century by a gardener who believed a prophecy promising a treasure inside. He found nothing.",
      fr: "Au XVIIᵉ siècle, un jardinier a creusé la tour Magne en croyant à une prophétie qui y promettait un trésor. Il n'a rien trouvé.",
    },
  },

  // ── Montpellier Saint-Roch ─────────────────────────────
  {
    id: "place-comedie",
    stationId: "87773002",
    category: "heritage",
    lat: 43.6087,
    lon: 3.8799,
    title: { en: "Place de la Comédie", fr: "Place de la Comédie" },
    era: { en: "19th century", fr: "XIXᵉ siècle" },
    summary: {
      en: "Montpellier's oval main square, nicknamed \"l'Œuf\", the egg.",
      fr: "La grande place ovale de Montpellier, surnommée « l'Œuf ».",
    },
    description: [
      {
        en: "The square takes its name from the theatre that has stood here since the 18th century; the current Opéra Comédie dates from 1888. Its oval shape, traced by old buildings, earned it the nickname \"the Egg\".",
        fr: "La place doit son nom au théâtre présent ici depuis le XVIIIᵉ siècle ; l'actuel Opéra Comédie date de 1888. Sa forme ovale, dessinée par les anciens immeubles, lui vaut le surnom de « l'Œuf ».",
      },
      {
        en: "In the centre, the Fountain of the Three Graces shows the daughters of Zeus. The square is now fully pedestrian and crossed by the tramway.",
        fr: "Au centre, la fontaine des Trois Grâces représente les filles de Zeus. La place est entièrement piétonne et traversée par le tramway.",
      },
    ],
    didYouKnow: {
      en: "The Three Graces in the fountain are a copy; the 18th-century original is kept inside the Opéra to protect it.",
      fr: "Les Trois Grâces de la fontaine sont une copie : l'original du XVIIIᵉ siècle est conservé à l'intérieur de l'Opéra pour le protéger.",
    },
  },
  {
    id: "peyrou",
    stationId: "87773002",
    category: "engineering",
    lat: 43.6113,
    lon: 3.8701,
    title: { en: "Promenade du Peyrou", fr: "Promenade du Peyrou" },
    era: { en: "17th – 18th century", fr: "XVIIᵉ – XVIIIᵉ siècle" },
    summary: {
      en: "A royal terrace with a triumphal arch, a water tower and a long stone aqueduct.",
      fr: "Une terrasse royale avec un arc de triomphe, un château d'eau et un long aqueduc de pierre.",
    },
    description: [
      {
        en: "The promenade was laid out on the highest point of the old town to honour Louis XIV, whose equestrian statue stands in the middle. The Arc de Triomphe at the entrance was built in the 1690s.",
        fr: "La promenade est aménagée sur le point le plus haut de la vieille ville pour honorer Louis XIV, dont la statue équestre trône au centre. L'arc de triomphe de l'entrée date des années 1690.",
      },
      {
        en: "At the far end, the hexagonal water tower received water from the Saint-Clément aqueduct, built in the 18th century to bring water from a spring about 14 km away. Its double row of arches is still standing.",
        fr: "Au bout, le château d'eau hexagonal recevait l'eau de l'aqueduc Saint-Clément, construit au XVIIIᵉ siècle pour amener l'eau d'une source située à environ 14 km. Sa double rangée d'arches est toujours debout.",
      },
    ],
    didYouKnow: {
      en: "The aqueduct was designed by Henri Pitot, the scientist who also invented the Pitot tube still used to measure an aircraft's speed.",
      fr: "L'aqueduc a été conçu par Henri Pitot, le savant qui a aussi inventé le tube de Pitot, toujours utilisé pour mesurer la vitesse des avions.",
    },
  },
  {
    id: "musee-fabre",
    stationId: "87773002",
    category: "museum",
    lat: 43.6117,
    lon: 3.8802,
    title: { en: "Musée Fabre", fr: "Musée Fabre" },
    era: { en: "Founded in 1825", fr: "Fondé en 1825" },
    summary: {
      en: "A major fine-arts museum, from old masters to Pierre Soulages.",
      fr: "Un grand musée des beaux-arts, des maîtres anciens à Pierre Soulages.",
    },
    description: [
      {
        en: "The museum was founded around the collection given to the city by the painter François-Xavier Fabre, who had lived in Italy for many years. It covers European painting from the Renaissance to the present day.",
        fr: "Le musée est né de la collection offerte à la ville par le peintre François-Xavier Fabre, qui avait longtemps vécu en Italie. Il couvre la peinture européenne de la Renaissance à nos jours.",
      },
      {
        en: "Do not miss the rooms dedicated to Frédéric Bazille, a Montpellier painter close to the Impressionists, and the large black canvases by Pierre Soulages.",
        fr: "À ne pas manquer : les salles consacrées à Frédéric Bazille, peintre montpelliérain proche des impressionnistes, et les grandes toiles noires de Pierre Soulages.",
      },
    ],
    didYouKnow: {
      en: "Bazille was killed in 1870 during the Franco-Prussian War, aged 28, just as his friends Monet and Renoir were starting out.",
      fr: "Bazille est mort en 1870 pendant la guerre franco-prussienne, à 28 ans, au moment où ses amis Monet et Renoir faisaient leurs débuts.",
    },
  },

  // ── Perpignan ──────────────────────────────────────────
  {
    id: "palais-majorque",
    stationId: "87784009",
    category: "heritage",
    lat: 42.6939,
    lon: 2.8957,
    title: { en: "Palace of the Kings of Majorca", fr: "Palais des rois de Majorque" },
    era: { en: "Late 13th century", fr: "Fin du XIIIᵉ siècle" },
    summary: {
      en: "The palace of a short-lived Mediterranean kingdom whose capital was Perpignan.",
      fr: "Le palais d'un royaume méditerranéen éphémère dont Perpignan était la capitale.",
    },
    description: [
      {
        en: "From 1276 to 1344, the Kingdom of Majorca stretched from the Balearic Islands to Roussillon and Montpellier. Its kings built this palace on a hill above Perpignan, around a large arcaded courtyard.",
        fr: "De 1276 à 1344, le royaume de Majorque s'étendait des Baléares au Roussillon et à Montpellier. Ses rois ont bâti ce palais sur une colline dominant Perpignan, autour d'une grande cour à arcades.",
      },
      {
        en: "It has two chapels on top of each other: the lower one for the court, the upper one for the royal family. Later, Vauban surrounded the palace with brick fortifications that are still visible.",
        fr: "Il compte deux chapelles superposées : celle du bas pour la cour, celle du haut pour la famille royale. Plus tard, Vauban a entouré le palais de fortifications en brique encore visibles.",
      },
    ],
    didYouKnow: {
      en: "Perpignan became French only in 1659, with the Treaty of the Pyrenees — before that, it was Catalan and then Spanish.",
      fr: "Perpignan n'est devenue française qu'en 1659, avec le traité des Pyrénées — avant, elle était catalane, puis espagnole.",
    },
  },
  {
    id: "castillet",
    stationId: "87784009",
    category: "museum",
    lat: 42.7006,
    lon: 2.8939,
    title: { en: "Le Castillet", fr: "Le Castillet" },
    era: { en: "14th century", fr: "XIVᵉ siècle" },
    summary: {
      en: "The red-brick gate tower that has become the symbol of Perpignan.",
      fr: "La porte fortifiée en brique rouge devenue le symbole de Perpignan.",
    },
    description: [
      {
        en: "Built in the 14th century as a gate in the city walls, the Castillet later served as a prison. When the walls were demolished in the early 20th century, it was kept as a landmark.",
        fr: "Construit au XIVᵉ siècle comme porte des remparts, le Castillet a ensuite servi de prison. Quand les murailles ont été rasées au début du XXᵉ siècle, il a été conservé comme emblème.",
      },
      {
        en: "Today it houses the Casa Pairal, a museum of Catalan arts and traditions: furniture, costumes, tools and objects of daily life in Roussillon. The top offers a view of the Canigou mountain.",
        fr: "Il abrite aujourd'hui la Casa Pairal, musée des arts et traditions catalanes : mobilier, costumes, outils et objets de la vie quotidienne en Roussillon. Du sommet, on voit le Canigou.",
      },
    ],
    didYouKnow: {
      en: "The Canigou, visible from the top, is a sacred mountain for Catalans: every June, a flame lit at its summit is carried to light the Saint John's Eve bonfires.",
      fr: "Le Canigou, visible du sommet, est la montagne sacrée des Catalans : chaque juin, une flamme allumée au sommet est portée pour embraser les feux de la Saint-Jean.",
    },
  },

  // ── Albi Ville ─────────────────────────────────────────
  {
    id: "sainte-cecile",
    stationId: "87615005",
    category: "heritage",
    lat: 43.9286,
    lon: 2.1426,
    title: { en: "Albi Cathedral (Sainte-Cécile)", fr: "Cathédrale Sainte-Cécile" },
    era: { en: "1282 – 1480", fr: "1282 – 1480" },
    summary: {
      en: "The largest brick cathedral in the world, built like a fortress.",
      fr: "La plus grande cathédrale de brique du monde, bâtie comme une forteresse.",
    },
    description: [
      {
        en: "Construction began in 1282, after the crusade against the Cathars. The bishop wanted a building that showed the power of the Church — hence its smooth, windowless lower walls that look like a castle's.",
        fr: "Sa construction commence en 1282, après la croisade contre les cathares. L'évêque voulait un édifice qui affirme la puissance de l'Église — d'où ses murs lisses et aveugles en partie basse, comme ceux d'un château.",
      },
      {
        en: "The contrast inside is striking: every surface is painted. The Last Judgement on the west wall, painted at the end of the 15th century, is one of the largest of its time. The Episcopal City of Albi is a UNESCO site since 2010.",
        fr: "À l'intérieur, le contraste est saisissant : tout est peint. Le Jugement dernier du mur ouest, réalisé à la fin du XVᵉ siècle, est l'un des plus grands de son époque. La cité épiscopale d'Albi est inscrite à l'UNESCO depuis 2010.",
      },
    ],
    didYouKnow: {
      en: "Brick was chosen because the region had clay but very little good building stone.",
      fr: "La brique s'est imposée parce que la région avait de l'argile, mais très peu de bonne pierre à bâtir.",
    },
  },
  {
    id: "musee-lautrec",
    stationId: "87615005",
    category: "museum",
    lat: 43.9292,
    lon: 2.1431,
    title: { en: "Toulouse-Lautrec Museum", fr: "Musée Toulouse-Lautrec" },
    era: { en: "Opened in 1922", fr: "Ouvert en 1922" },
    summary: {
      en: "The world's largest collection of Toulouse-Lautrec, in a medieval bishop's palace.",
      fr: "La plus grande collection au monde de Toulouse-Lautrec, dans un palais d'évêques médiéval.",
    },
    description: [
      {
        en: "Henri de Toulouse-Lautrec was born in Albi in 1864. After his death, his mother gave his works to the city, which displayed them in the Palais de la Berbie, the former bishops' fortress next to the cathedral.",
        fr: "Henri de Toulouse-Lautrec est né à Albi en 1864. Après sa mort, sa mère a donné ses œuvres à la ville, qui les expose au palais de la Berbie, l'ancienne forteresse des évêques voisine de la cathédrale.",
      },
      {
        en: "You can see his paintings of Montmartre cabarets and all his famous posters, including those for the Moulin Rouge. The palace gardens overlook the river Tarn.",
        fr: "On y voit ses tableaux des cabarets de Montmartre et toutes ses célèbres affiches, dont celles du Moulin Rouge. Les jardins du palais dominent le Tarn.",
      },
    ],
    didYouKnow: {
      en: "Lautrec broke both legs as a teenager; they stopped growing, which is why he was about 1.52 m tall as an adult.",
      fr: "Adolescent, Lautrec s'est fracturé les deux jambes ; elles ont cessé de grandir, d'où sa taille d'environ 1,52 m à l'âge adulte.",
    },
  },

  // ── Sète ───────────────────────────────────────────────
  {
    id: "cimetiere-marin",
    stationId: "87773200",
    category: "heritage",
    lat: 43.3947,
    lon: 3.6917,
    title: { en: "Le Cimetière marin", fr: "Le Cimetière marin" },
    era: { en: "19th century", fr: "XIXᵉ siècle" },
    summary: {
      en: "A cemetery on a slope above the sea, made famous by a poem by Paul Valéry.",
      fr: "Un cimetière en pente au-dessus de la mer, rendu célèbre par un poème de Paul Valéry.",
    },
    description: [
      {
        en: "Terraced on the side of Mont Saint-Clair, the cemetery faces the Mediterranean. Paul Valéry, born in Sète, described it in his 1920 poem \"Le Cimetière marin\", one of the best-known poems in French literature.",
        fr: "Étagé sur le flanc du mont Saint-Clair, le cimetière fait face à la Méditerranée. Paul Valéry, né à Sète, l'a décrit en 1920 dans « Le Cimetière marin », l'un des poèmes les plus connus de la littérature française.",
      },
      {
        en: "Valéry is buried here. Next door, the Musée Paul Valéry presents his life and works as well as Mediterranean art.",
        fr: "Valéry y est enterré. Juste à côté, le musée Paul-Valéry présente sa vie et son œuvre, ainsi que de l'art méditerranéen.",
      },
    ],
    didYouKnow: {
      en: "Georges Brassens, the other famous Sétois, is buried in a different cemetery: Le Py, by the Étang de Thau.",
      fr: "Georges Brassens, l'autre célèbre Sétois, repose dans un autre cimetière : celui du Py, au bord de l'étang de Thau.",
    },
  },
  {
    id: "mont-saint-clair",
    stationId: "87773200",
    category: "nature",
    lat: 43.402,
    lon: 3.6845,
    title: { en: "Mont Saint-Clair", fr: "Mont Saint-Clair" },
    era: { en: "Natural site", fr: "Site naturel" },
    summary: {
      en: "The hill that overlooks Sète, between the sea and the Étang de Thau.",
      fr: "La colline qui domine Sète, entre la mer et l'étang de Thau.",
    },
    description: [
      {
        en: "Sète is built on a former island linked to the mainland by sand bars. Mont Saint-Clair is its high point: from the top you see the sea on one side and the Étang de Thau, with its oyster tables, on the other.",
        fr: "Sète est bâtie sur une ancienne île reliée au continent par des cordons de sable. Le mont Saint-Clair en est le sommet : on voit la mer d'un côté, et de l'autre l'étang de Thau et ses tables à huîtres.",
      },
      {
        en: "On clear days you can see the Pyrenees and the Canigou. The walk up is steep but short, through pine woods and small gardens.",
        fr: "Par temps clair, on aperçoit les Pyrénées et le Canigou. La montée est raide mais courte, à travers les pinèdes et les petits jardins.",
      },
    ],
    didYouKnow: {
      en: "The Étang de Thau is where the Canal du Midi ends — its water finally reaches the Mediterranean through Sète's port.",
      fr: "C'est dans l'étang de Thau que finit le canal du Midi — son eau rejoint ensuite la Méditerranée par le port de Sète.",
    },
  },

  // ── Lourdes ────────────────────────────────────────────
  {
    id: "chateau-lourdes",
    stationId: "87671339",
    category: "museum",
    lat: 43.0967,
    lon: -0.0492,
    title: { en: "Château fort de Lourdes", fr: "Château fort de Lourdes" },
    era: { en: "Middle Ages", fr: "Moyen Âge" },
    summary: {
      en: "A fortress on a rock, home to a museum of life in the Pyrenees.",
      fr: "Une forteresse sur un rocher, qui abrite un musée de la vie dans les Pyrénées.",
    },
    description: [
      {
        en: "Perched on a rocky spur, the castle guarded the entrance to the Pyrenean valleys. It was long disputed between the English and the French during the Hundred Years' War, then used as a state prison.",
        fr: "Perché sur un éperon rocheux, le château gardait l'entrée des vallées pyrénéennes. Longtemps disputé entre Anglais et Français pendant la guerre de Cent Ans, il a ensuite servi de prison d'État.",
      },
      {
        en: "Since 1921 it has housed the Musée pyrénéen: costumes, tools, farming life, and the history of the first climbers of the Pyrenees.",
        fr: "Depuis 1921, il abrite le Musée pyrénéen : costumes, outils, vie pastorale, et l'histoire des premiers ascensionnistes des Pyrénées.",
      },
    ],
    didYouKnow: {
      en: "The word \"pyrénéisme\" names the art of climbing in the Pyrenees, as \"alpinism\" does for the Alps.",
      fr: "Le mot « pyrénéisme » désigne l'art de gravir les Pyrénées, comme « alpinisme » pour les Alpes.",
    },
  },
  {
    id: "sanctuaire-lourdes",
    stationId: "87671339",
    category: "heritage",
    lat: 43.0975,
    lon: -0.0577,
    title: { en: "Sanctuary of Our Lady of Lourdes", fr: "Sanctuaire Notre-Dame de Lourdes" },
    era: { en: "Since 1858", fr: "Depuis 1858" },
    summary: {
      en: "One of the largest pilgrimage sites in the world, born from a young girl's visions.",
      fr: "L'un des plus grands lieux de pèlerinage au monde, né des visions d'une jeune fille.",
    },
    description: [
      {
        en: "In 1858, Bernadette Soubirous, a 14-year-old from a poor family, said she saw a lady in the Massabielle grotto. The site became a major Catholic pilgrimage, which turned Lourdes from a small market town into a city of hotels.",
        fr: "En 1858, Bernadette Soubirous, 14 ans, issue d'une famille pauvre, dit voir une dame dans la grotte de Massabielle. Le lieu devient un grand pèlerinage catholique, qui transforme le petit bourg de Lourdes en ville d'hôtels.",
      },
      {
        en: "The sanctuary includes the grotto, several basilicas stacked on the hillside, and one of the largest underground churches in the world, the Basilica of Saint Pius X.",
        fr: "Le sanctuaire comprend la grotte, plusieurs basiliques étagées sur la colline et l'une des plus grandes églises souterraines au monde, la basilique Saint-Pie-X.",
      },
    ],
    didYouKnow: {
      en: "Lourdes has more hotel rooms than any other French city except Paris.",
      fr: "Lourdes compte plus de chambres d'hôtel que n'importe quelle autre ville française, Paris excepté.",
    },
  },

  // ── Cahors ─────────────────────────────────────────────
  {
    id: "pont-valentre",
    stationId: "87613000",
    category: "engineering",
    lat: 44.4451,
    lon: 1.4317,
    title: { en: "Pont Valentré", fr: "Pont Valentré" },
    era: { en: "14th century", fr: "XIVᵉ siècle" },
    summary: {
      en: "A fortified bridge with three towers over the river Lot.",
      fr: "Un pont fortifié à trois tours qui enjambe le Lot.",
    },
    description: [
      {
        en: "Built in the 14th century, the bridge was both a crossing and a defence: its three square towers could close the passage to attackers. It is one of the best-preserved fortified bridges in Europe.",
        fr: "Bâti au XIVᵉ siècle, le pont était à la fois un passage et une défense : ses trois tours carrées pouvaient fermer l'accès aux assaillants. C'est l'un des ponts fortifiés les mieux conservés d'Europe.",
      },
      {
        en: "It lies on the Way of St James and is part of the UNESCO listing. The walk from the station takes you through the old town down to the river.",
        fr: "Il se trouve sur le chemin de Saint-Jacques et fait partie de l'inscription à l'UNESCO. Depuis la gare, on y descend par la vieille ville jusqu'à la rivière.",
      },
    ],
    didYouKnow: {
      en: "Look at the top of the central tower: a small stone devil clings to it. The restorer added it in the 19th century to illustrate the legend of a pact between the builder and the Devil.",
      fr: "Regardez le haut de la tour centrale : un petit diable de pierre s'y accroche. Le restaurateur l'a ajouté au XIXᵉ siècle pour illustrer la légende d'un pacte entre le bâtisseur et le Diable.",
    },
  },
  {
    id: "cathedrale-cahors",
    stationId: "87613000",
    category: "heritage",
    lat: 44.4479,
    lon: 1.4418,
    title: { en: "Cahors Cathedral", fr: "Cathédrale Saint-Étienne" },
    era: { en: "12th century", fr: "XIIᵉ siècle" },
    summary: {
      en: "A Romanesque cathedral topped with two huge domes, rare in France.",
      fr: "Une cathédrale romane coiffée de deux immenses coupoles, rares en France.",
    },
    description: [
      {
        en: "Instead of a long vaulted nave, the cathedral is covered by two domes on pendentives, a style inspired by Byzantine churches. Its domes are among the largest of their kind in France.",
        fr: "Au lieu d'une longue nef voûtée, la cathédrale est couverte de deux coupoles sur pendentifs, un style inspiré des églises byzantines. Elles comptent parmi les plus grandes de ce type en France.",
      },
      {
        en: "The north portal shows a carved Ascension of Christ, and a Gothic cloister was added on the south side at the end of the Middle Ages.",
        fr: "Le portail nord présente une Ascension du Christ sculptée, et un cloître gothique a été ajouté au sud à la fin du Moyen Âge.",
      },
    ],
    didYouKnow: {
      en: "One of the domes still has its early-14th-century paintings, showing eight prophets.",
      fr: "L'une des coupoles a gardé ses peintures du début du XIVᵉ siècle, qui représentent huit prophètes.",
    },
  },

  // ── Narbonne ───────────────────────────────────────────
  {
    id: "horreum",
    stationId: "87781104",
    category: "heritage",
    lat: 43.1857,
    lon: 3.0047,
    title: { en: "Roman Horreum", fr: "Horreum romain" },
    era: { en: "1st century BC", fr: "Iᵉʳ siècle av. J.-C." },
    summary: {
      en: "Underground galleries that served as a warehouse in Roman Narbonne.",
      fr: "Des galeries souterraines qui servaient d'entrepôt dans la Narbonne romaine.",
    },
    description: [
      {
        en: "Narbonne, founded in 118 BC as Narbo Martius, was the first Roman colony in Gaul and a major port. The horreum is a network of underground galleries where goods were probably stored, cool and safe.",
        fr: "Narbonne, fondée en 118 av. J.-C. sous le nom de Narbo Martius, fut la première colonie romaine de Gaule et un grand port. L'horreum est un réseau de galeries souterraines où l'on stockait sans doute les marchandises, au frais et à l'abri.",
      },
      {
        en: "Only the underground part has survived: the building above has disappeared under the streets of the modern city.",
        fr: "Seul le sous-sol a survécu : le bâtiment du dessus a disparu sous les rues de la ville actuelle.",
      },
    ],
    didYouKnow: {
      en: "The Via Domitia, the first Roman road in Gaul, passed through Narbonne — a section of its paving is visible on the town hall square.",
      fr: "La via Domitia, première route romaine de Gaule, passait par Narbonne — un tronçon de son dallage est visible sur la place de l'Hôtel-de-Ville.",
    },
  },
  {
    id: "palais-archeveques",
    stationId: "87781104",
    category: "museum",
    lat: 43.1842,
    lon: 3.0037,
    title: { en: "Archbishops' Palace", fr: "Palais des Archevêques" },
    era: { en: "12th – 14th century", fr: "XIIᵉ – XIVᵉ siècle" },
    summary: {
      en: "A fortified palace that now houses the town hall and museums.",
      fr: "Un palais fortifié qui abrite aujourd'hui l'hôtel de ville et des musées.",
    },
    description: [
      {
        en: "The archbishops of Narbonne were powerful lords; their palace has towers and walls like a castle. It forms one ensemble with the Cathedral of Saint-Just-et-Saint-Pasteur, whose choir is very tall but whose nave was never built.",
        fr: "Les archevêques de Narbonne étaient de puissants seigneurs : leur palais a des tours et des murailles de château. Il forme un ensemble avec la cathédrale Saint-Just-et-Saint-Pasteur, au chœur immense mais dont la nef n'a jamais été construite.",
      },
      {
        en: "You can climb the Donjon Gilles Aycelin for a view over the city and, on clear days, as far as the Pyrenees.",
        fr: "On peut monter au donjon Gilles-Aycelin pour une vue sur la ville et, par temps clair, jusqu'aux Pyrénées.",
      },
    ],
    didYouKnow: {
      en: "The cathedral's nave was never built because continuing it would have meant tearing down the city's Roman walls.",
      fr: "La nef de la cathédrale n'a jamais été bâtie : la poursuivre aurait obligé à abattre les remparts de la ville.",
    },
  },

  // ── Béziers ────────────────────────────────────────────
  {
    id: "fonseranes",
    stationId: "87781005",
    category: "engineering",
    lat: 43.3308,
    lon: 3.2001,
    title: { en: "Fonseranes Locks", fr: "Écluses de Fonseranes" },
    era: { en: "17th century", fr: "XVIIᵉ siècle" },
    summary: {
      en: "A staircase of locks that lifts boats about 21 m on the Canal du Midi.",
      fr: "Un escalier d'écluses qui fait monter les bateaux d'environ 21 m sur le canal du Midi.",
    },
    description: [
      {
        en: "To climb the hill west of Béziers, Riquet built a chain of eight basins with nine gates, over some 300 m. Boats go up or down step by step, the water of one basin filling the next.",
        fr: "Pour franchir la colline à l'ouest de Béziers, Riquet a construit une chaîne de huit bassins et neuf portes, sur environ 300 m. Les bateaux montent ou descendent marche par marche, l'eau d'un bassin remplissant le suivant.",
      },
      {
        en: "Nearby, the Orb canal bridge (1858) carries the canal over the river — a bridge for boats.",
        fr: "Tout près, le pont-canal de l'Orb (1858) fait passer le canal au-dessus de la rivière — un pont pour les bateaux.",
      },
    ],
    didYouKnow: {
      en: "Pierre-Paul Riquet was born in Béziers; his statue stands on the city's main promenade, the Allées Paul-Riquet.",
      fr: "Pierre-Paul Riquet est né à Béziers ; sa statue trône sur la grande promenade de la ville, les allées Paul-Riquet.",
    },
  },
  {
    id: "saint-nazaire-beziers",
    stationId: "87781005",
    category: "heritage",
    lat: 43.3407,
    lon: 3.21,
    title: { en: "Saint-Nazaire Cathedral", fr: "Cathédrale Saint-Nazaire" },
    era: { en: "13th – 14th century", fr: "XIIIᵉ – XIVᵉ siècle" },
    summary: {
      en: "A fortified Gothic cathedral overlooking the river Orb.",
      fr: "Une cathédrale gothique fortifiée qui domine la rivière Orb.",
    },
    description: [
      {
        en: "The cathedral was rebuilt after Béziers was sacked in 1209 during the crusade against the Cathars. Its massive tower and walls give it the look of a fortress.",
        fr: "La cathédrale a été reconstruite après le sac de Béziers en 1209, pendant la croisade contre les cathares. Sa tour massive et ses murs lui donnent l'allure d'une forteresse.",
      },
      {
        en: "From the terrace behind it, you look down on the Orb, the old bridge and the plain stretching towards the sea.",
        fr: "Depuis la terrasse à l'arrière, on domine l'Orb, le pont Vieux et la plaine qui s'étend vers la mer.",
      },
    ],
    didYouKnow: {
      en: "The sack of 1209 is linked to a famous phrase attributed to the papal legate: \"Kill them all, God will know His own.\" Historians doubt he ever said it.",
      fr: "Le sac de 1209 est associé à une phrase célèbre attribuée au légat du pape : « Tuez-les tous, Dieu reconnaîtra les siens. » Les historiens doutent qu'il l'ait jamais prononcée.",
    },
  },

  // ── Foix ───────────────────────────────────────────────
  {
    id: "chateau-foix",
    stationId: "87611616",
    category: "heritage",
    lat: 42.9656,
    lon: 1.605,
    title: { en: "Château de Foix", fr: "Château de Foix" },
    era: { en: "From the 10th century", fr: "À partir du Xᵉ siècle" },
    summary: {
      en: "A three-tower castle on a rock, seat of the powerful Counts of Foix.",
      fr: "Un château à trois tours sur un rocher, siège des puissants comtes de Foix.",
    },
    description: [
      {
        en: "The castle controlled the road into the Ariège valleys. Its counts were among the great lords of the south; the most famous, Gaston Fébus, was known for his court, his wars and his book on hunting.",
        fr: "Le château contrôlait la route des vallées de l'Ariège. Ses comtes comptaient parmi les grands seigneurs du Midi ; le plus célèbre, Gaston Fébus, est connu pour sa cour, ses guerres et son livre sur la chasse.",
      },
      {
        en: "Inside, a museum recreates daily life in a medieval castle, with costumed demonstrations in summer.",
        fr: "À l'intérieur, un musée fait revivre la vie quotidienne d'un château médiéval, avec des démonstrations en costume l'été.",
      },
    ],
    didYouKnow: {
      en: "During the crusade against the Cathars, Simon de Montfort burned the town of Foix but never managed to take the castle.",
      fr: "Pendant la croisade contre les cathares, Simon de Montfort a incendié la ville de Foix sans jamais parvenir à prendre le château.",
    },
  },

  // ── Collioure ──────────────────────────────────────────
  {
    id: "chateau-collioure",
    stationId: "87784256",
    category: "heritage",
    lat: 42.5255,
    lon: 3.0838,
    title: { en: "Royal Castle of Collioure", fr: "Château royal de Collioure" },
    era: { en: "13th – 17th century", fr: "XIIIᵉ – XVIIᵉ siècle" },
    summary: {
      en: "A seaside fortress used by the Kings of Majorca, then reinforced by Vauban.",
      fr: "Une forteresse au bord de l'eau, résidence des rois de Majorque puis renforcée par Vauban.",
    },
    description: [
      {
        en: "Set between two beaches, the castle was a summer residence of the Kings of Majorca. When Roussillon became French, Vauban reinforced it with thick sloping walls designed to resist cannon fire.",
        fr: "Posé entre deux plages, le château était une résidence d'été des rois de Majorque. Quand le Roussillon devient français, Vauban le renforce de murs épais et inclinés, conçus pour résister aux boulets de canon.",
      },
      {
        en: "From the ramparts you can see the whole bay, the old port and the bell tower of Notre-Dame-des-Anges.",
        fr: "Depuis les remparts, on voit toute la baie, le vieux port et le clocher de Notre-Dame-des-Anges.",
      },
    ],
    didYouKnow: {
      en: "Sloped walls were a response to artillery: a cannonball hitting at an angle tends to glance off instead of breaking the stone.",
      fr: "Les murs inclinés répondent à l'artillerie : un boulet qui frappe de biais a tendance à ricocher au lieu de briser la pierre.",
    },
  },
  {
    id: "notre-dame-des-anges",
    stationId: "87784256",
    category: "heritage",
    lat: 42.5269,
    lon: 3.0846,
    title: { en: "Notre-Dame-des-Anges", fr: "Notre-Dame-des-Anges" },
    era: { en: "17th century", fr: "XVIIᵉ siècle" },
    summary: {
      en: "A church with its feet in the sea, whose bell tower was once a lighthouse.",
      fr: "Une église les pieds dans l'eau, dont le clocher était autrefois un phare.",
    },
    description: [
      {
        en: "The church was built in the 17th century right on the shore. Its round bell tower, with a pink dome, was originally the town's medieval lighthouse.",
        fr: "L'église a été construite au XVIIᵉ siècle au ras du rivage. Son clocher rond, coiffé d'un dôme rose, était à l'origine le phare médiéval de la ville.",
      },
      {
        en: "Inside, the gilded wooden altarpieces are typical of Catalan Baroque art.",
        fr: "À l'intérieur, les retables en bois doré sont typiques de l'art baroque catalan.",
      },
    ],
    didYouKnow: {
      en: "In 1905, Henri Matisse and André Derain painted Collioure in pure, bright colours — critics called them \"fauves\" (wild beasts), and Fauvism was born.",
      fr: "En 1905, Henri Matisse et André Derain peignent Collioure en couleurs pures et vives — la critique les traite de « fauves », et le fauvisme est né.",
    },
  },

  // ── Millau ─────────────────────────────────────────────
  {
    id: "viaduc-millau",
    stationId: "87783001",
    category: "engineering",
    lat: 44.0777,
    lon: 3.0225,
    title: { en: "Millau Viaduct", fr: "Viaduc de Millau" },
    era: { en: "Opened in 2004", fr: "Inauguré en 2004" },
    summary: {
      en: "A cable-stayed bridge with the tallest pylon of any bridge in the world.",
      fr: "Un pont à haubans dont un pylône est le plus haut de tous les ponts du monde.",
    },
    description: [
      {
        en: "The viaduct carries the A75 motorway over the Tarn valley, about 270 m above the river. It is some 2.5 km long and rests on seven piers; its highest point reaches 343 m, taller than the Eiffel Tower.",
        fr: "Le viaduc fait passer l'autoroute A75 au-dessus de la vallée du Tarn, à environ 270 m de la rivière. Long d'environ 2,5 km, il repose sur sept piles ; son point le plus haut atteint 343 m, plus que la tour Eiffel.",
      },
      {
        en: "It was designed by engineer Michel Virlogeux and architect Norman Foster. The visitor area at the foot of the bridge explains how the deck was slid into place from both sides of the valley.",
        fr: "Il a été conçu par l'ingénieur Michel Virlogeux et l'architecte Norman Foster. L'aire d'accueil au pied du pont explique comment le tablier a été poussé depuis les deux rives de la vallée.",
      },
    ],
    didYouKnow: {
      en: "The deck is very slightly curved (about 20 km radius), so drivers have a better sense of the bridge and don't feel like they are driving into the void.",
      fr: "Le tablier est très légèrement courbé (environ 20 km de rayon) pour que les conducteurs perçoivent mieux le pont et n'aient pas l'impression de rouler vers le vide.",
    },
  },

  // ── Moissac ────────────────────────────────────────────
  {
    id: "abbaye-moissac",
    stationId: "87611889",
    category: "heritage",
    lat: 44.1052,
    lon: 1.0845,
    title: { en: "Moissac Abbey", fr: "Abbaye Saint-Pierre de Moissac" },
    era: { en: "Completed in 1100", fr: "Achevée en 1100" },
    summary: {
      en: "A Romanesque cloister and portal that are masterpieces of medieval sculpture.",
      fr: "Un cloître et un portail romans, chefs-d'œuvre de la sculpture médiévale.",
    },
    description: [
      {
        en: "The cloister, finished in 1100, is the oldest Romanesque cloister with carved capitals to survive in this state. Its capitals tell stories from the Bible and the lives of saints, like a picture book in stone.",
        fr: "Le cloître, achevé en 1100, est le plus ancien cloître roman à chapiteaux sculptés conservé dans cet état. Ses chapiteaux racontent des scènes de la Bible et de la vie des saints, comme un livre d'images en pierre.",
      },
      {
        en: "The south portal shows Christ surrounded by the elders of the Apocalypse. The abbey is a stop on the Way of St James.",
        fr: "Le portail sud montre le Christ entouré des vieillards de l'Apocalypse. L'abbaye est une étape du chemin de Saint-Jacques.",
      },
    ],
    didYouKnow: {
      en: "In the 1850s, the railway line from Bordeaux to Sète was planned straight through the cloister. It was saved, but part of the abbey was demolished for the tracks.",
      fr: "Dans les années 1850, la voie ferrée Bordeaux–Sète devait traverser le cloître. Il a été sauvé, mais une partie de l'abbaye a été démolie pour les rails.",
    },
  },

  // ── Figeac ─────────────────────────────────────────────
  {
    id: "musee-champollion",
    stationId: "87613091",
    category: "museum",
    lat: 44.6083,
    lon: 2.0318,
    title: { en: "Champollion Museum", fr: "Musée Champollion" },
    era: { en: "Writing of the world", fr: "Les écritures du monde" },
    summary: {
      en: "A museum of the world's writing systems, in the birthplace of the man who decoded hieroglyphs.",
      fr: "Un musée des écritures du monde, dans la maison natale de celui qui a déchiffré les hiéroglyphes.",
    },
    description: [
      {
        en: "Jean-François Champollion was born in Figeac in 1790. In 1822, by comparing the Greek and Egyptian texts of the Rosetta Stone, he showed how hieroglyphs worked: a mix of signs for sounds and signs for ideas.",
        fr: "Jean-François Champollion est né à Figeac en 1790. En 1822, en comparant les textes grec et égyptien de la pierre de Rosette, il montre comment fonctionnent les hiéroglyphes : un mélange de signes-sons et de signes-idées.",
      },
      {
        en: "The museum tells the history of writing, from cuneiform tablets to the alphabet. Next to it, the Place des Écritures has a giant replica of the Rosetta Stone carved in the ground.",
        fr: "Le musée raconte l'histoire de l'écriture, des tablettes cunéiformes à l'alphabet. Juste à côté, la place des Écritures présente une réplique géante de la pierre de Rosette gravée dans le sol.",
      },
    ],
    didYouKnow: {
      en: "The Rosetta Stone carries the same decree in three scripts: hieroglyphs, demotic and ancient Greek — that is what made it a key.",
      fr: "La pierre de Rosette porte le même décret en trois écritures : hiéroglyphes, démotique et grec ancien — c'est ce qui en a fait une clé.",
    },
  },

  // ── Rodez ──────────────────────────────────────────────
  {
    id: "musee-soulages",
    stationId: "87613422",
    category: "museum",
    lat: 44.3484,
    lon: 2.5714,
    title: { en: "Soulages Museum", fr: "Musée Soulages" },
    era: { en: "Opened in 2014", fr: "Ouvert en 2014" },
    summary: {
      en: "A museum devoted to Pierre Soulages, the painter of black and light.",
      fr: "Un musée consacré à Pierre Soulages, le peintre du noir et de la lumière.",
    },
    description: [
      {
        en: "Pierre Soulages was born in Rodez in 1919. He became famous for his \"outrenoir\" paintings: canvases covered in black, where the texture of the paint catches and reflects the light.",
        fr: "Pierre Soulages est né à Rodez en 1919. Il est célèbre pour ses « outrenoirs » : des toiles couvertes de noir, où la matière de la peinture accroche et renvoie la lumière.",
      },
      {
        en: "The building, clad in rusted Corten steel, was designed by the Catalan firm RCR Arquitectes. The museum also shows his work on the stained-glass windows of the Abbey of Conques.",
        fr: "Le bâtiment, habillé d'acier Corten rouillé, a été dessiné par l'agence catalane RCR Arquitectes. Le musée présente aussi son travail sur les vitraux de l'abbatiale de Conques.",
      },
    ],
    didYouKnow: {
      en: "RCR Arquitectes, who designed the museum, received the Pritzker Prize — architecture's highest award — in 2017.",
      fr: "RCR Arquitectes, l'agence qui a conçu le musée, a reçu le prix Pritzker — la plus haute distinction en architecture — en 2017.",
    },
  },
  {
    id: "cathedrale-rodez",
    stationId: "87613422",
    category: "heritage",
    lat: 44.3508,
    lon: 2.5747,
    title: { en: "Rodez Cathedral", fr: "Cathédrale Notre-Dame de Rodez" },
    era: { en: "1277 – 16th century", fr: "1277 – XVIᵉ siècle" },
    summary: {
      en: "A pink sandstone Gothic cathedral with a bell tower of about 87 m.",
      fr: "Une cathédrale gothique en grès rose, avec un clocher d'environ 87 m.",
    },
    description: [
      {
        en: "Construction began in 1277 and took about three centuries. The pink sandstone gives the building its colour, which changes with the light during the day.",
        fr: "Commencée en 1277, la construction a duré environ trois siècles. Le grès rose donne sa couleur à l'édifice, qui change avec la lumière au fil de la journée.",
      },
      {
        en: "The west façade has almost no door and looks like a wall: it was part of the city's fortifications. The richly carved bell tower is a late Gothic masterpiece.",
        fr: "La façade ouest n'a presque pas de porte et ressemble à un mur : elle faisait partie des remparts de la ville. Le clocher, richement sculpté, est un chef-d'œuvre du gothique flamboyant.",
      },
    ],
    didYouKnow: {
      en: "The bell tower was rebuilt after a fire in 1510; its upper floors were finished in the 1520s.",
      fr: "Le clocher a été reconstruit après un incendie en 1510 ; ses étages supérieurs ont été achevés dans les années 1520.",
    },
  },
  // ── Nouveaux thèmes : musique, sport, sciences, savoir-faire ──
  {
    id: "halle-aux-grains",
    stationId: "87611004",
    category: "music",
    lat: 43.5995,
    lon: 1.4524,
    title: { en: "Halle aux Grains", fr: "Halle aux Grains" },
    era: { en: "Concert hall since 1974", fr: "Salle de concert depuis 1974" },
    summary: {
      en: "A former grain market turned into the home of the Orchestre national du Capitole.",
      fr: "Un ancien marché aux grains devenu la maison de l'Orchestre national du Capitole.",
    },
    description: [
      {
        en: "Built in the 1860s to trade wheat, this large hexagonal hall was later converted into a concert hall. Its seats surround the stage on several sides, so the audience sits close to the musicians.",
        fr: "Construite dans les années 1860 pour le commerce du blé, cette grande halle hexagonale a ensuite été transformée en salle de concert. Ses gradins entourent la scène sur plusieurs côtés : le public est tout près des musiciens.",
      },
      {
        en: "It is the home of the Orchestre national du Capitole de Toulouse, which became internationally known under the conductor Michel Plasson.",
        fr: "C'est la salle de l'Orchestre national du Capitole de Toulouse, devenu célèbre dans le monde entier sous la direction de Michel Plasson.",
      },
    ],
    didYouKnow: {
      en: "A concert hall inside an old market: a good example of a building given a new life instead of being torn down.",
      fr: "Une salle de concert dans un ancien marché : un bel exemple de bâtiment réutilisé plutôt que démoli.",
    },
  },
  {
    id: "corum",
    stationId: "87773002",
    category: "music",
    lat: 43.6143,
    lon: 3.882,
    title: { en: "Le Corum – Opéra Berlioz", fr: "Le Corum – Opéra Berlioz" },
    era: { en: "1990", fr: "1990" },
    summary: {
      en: "Montpellier's large concert hall, named after the composer Hector Berlioz.",
      fr: "La grande salle de concert de Montpellier, baptisée du nom du compositeur Hector Berlioz.",
    },
    description: [
      {
        en: "Designed by the architect Claude Vasconi, the Corum is both a conference centre and an opera house. Its main hall, the Opéra Berlioz, seats about 2,000 people.",
        fr: "Dessiné par l'architecte Claude Vasconi, le Corum est à la fois un palais des congrès et un opéra. Sa grande salle, l'Opéra Berlioz, accueille environ 2 000 spectateurs.",
      },
      {
        en: "The Orchestre national Montpellier Occitanie plays here, and every summer the building hosts concerts of the Festival Radio France Occitanie Montpellier.",
        fr: "L'Orchestre national Montpellier Occitanie y joue, et chaque été le bâtiment accueille des concerts du Festival Radio France Occitanie Montpellier.",
      },
    ],
    didYouKnow: {
      en: "Hector Berlioz, who gave his name to the hall, composed the Symphonie fantastique in 1830.",
      fr: "Hector Berlioz, qui a donné son nom à la salle, a composé la Symphonie fantastique en 1830.",
    },
  },
  {
    id: "espace-brassens",
    stationId: "87773200",
    category: "music",
    lat: 43.3966,
    lon: 3.6798,
    title: { en: "Espace Georges-Brassens", fr: "Espace Georges-Brassens" },
    era: { en: "Opened in 1991", fr: "Ouvert en 1991" },
    summary: {
      en: "A museum devoted to the singer-songwriter Georges Brassens, in the town where he was born.",
      fr: "Un musée consacré au chanteur Georges Brassens, dans la ville où il est né.",
    },
    description: [
      {
        en: "Georges Brassens was born in Sète in 1921. With his guitar, his pipe and his carefully written lyrics, he became one of the great French songwriters of the 20th century.",
        fr: "Georges Brassens est né à Sète en 1921. Avec sa guitare, sa pipe et ses textes ciselés, il est devenu l'un des grands auteurs de chansons françaises du XXᵉ siècle.",
      },
      {
        en: "Visitors walk through his life with headphones: his songs, his voice and his words play as you move from room to room. A good way to study poetry set to music.",
        fr: "La visite se fait avec un casque : chansons, voix et paroles de Brassens accompagnent chaque salle. Une belle façon d'étudier la poésie mise en musique.",
      },
    ],
    didYouKnow: {
      en: "Brassens rests in the Le Py cemetery, just across the road — not on the beach, as he had asked in his song « Supplique pour être enterré à la plage de Sète ».",
      fr: "Brassens repose au cimetière Le Py, juste en face — et non sur la plage, comme il le demandait dans sa chanson « Supplique pour être enterré à la plage de Sète ».",
    },
  },
  {
    id: "stadium-toulouse",
    stationId: "87611301",
    category: "sport",
    lat: 43.5833,
    lon: 1.4341,
    title: { en: "Stadium de Toulouse", fr: "Stadium de Toulouse" },
    era: { en: "1949", fr: "1949" },
    summary: {
      en: "The big stadium on an island in the Garonne, nicknamed « the little Wembley ».",
      fr: "Le grand stade posé sur une île de la Garonne, surnommé « le petit Wembley ».",
    },
    description: [
      {
        en: "The Stadium stands on the Île du Ramier, surrounded by the river. It is the home ground of the football club Toulouse FC and also hosts big rugby matches.",
        fr: "Le Stadium se dresse sur l'île du Ramier, entouré par le fleuve. C'est le stade du Toulouse FC, et il accueille aussi de grands matchs de rugby.",
      },
      {
        en: "It hosted matches of the 1998 Football World Cup and of the Rugby World Cups in 2007 and 2023.",
        fr: "Il a accueilli des matchs de la Coupe du monde de football 1998 et des Coupes du monde de rugby 2007 et 2023.",
      },
    ],
    didYouKnow: {
      en: "Its English-style stands, very close to the pitch, earned it the nickname « le petit Wembley ».",
      fr: "Ses tribunes à l'anglaise, tout près de la pelouse, lui ont valu le surnom de « petit Wembley ».",
    },
  },
  {
    id: "cnea-font-romeu",
    stationId: "87784819",
    category: "sport",
    lat: 42.5065,
    lon: 2.0432,
    title: { en: "National Altitude Training Centre", fr: "Centre national d'entraînement en altitude" },
    era: { en: "1967", fr: "1967" },
    summary: {
      en: "Where French athletes come to train at 1,850 m, reached by the little Yellow Train.",
      fr: "Là où les athlètes français viennent s'entraîner à 1 850 m, au bout du petit Train jaune.",
    },
    description: [
      {
        en: "The centre was built to prepare French athletes for the 1968 Olympic Games in Mexico City, held at more than 2,000 m of altitude.",
        fr: "Le centre a été construit pour préparer les athlètes français aux Jeux olympiques de 1968 à Mexico, disputés à plus de 2 000 m d'altitude.",
      },
      {
        en: "Up here the air contains less oxygen, so the body produces more red blood cells. Runners, swimmers and skiers still come for training camps.",
        fr: "En altitude, l'air contient moins d'oxygène : le corps fabrique alors plus de globules rouges. Coureurs, nageurs et skieurs y viennent encore en stage.",
      },
    ],
    didYouKnow: {
      en: "It is a good case study for biology lessons: why do athletes train in the mountains before a competition?",
      fr: "Un bon sujet pour un cours de SVT : pourquoi les sportifs s'entraînent-ils en montagne avant une compétition ?",
    },
  },
  {
    id: "joutes-sete",
    stationId: "87773200",
    category: "sport",
    lat: 43.4035,
    lon: 3.6955,
    title: { en: "Water jousting on the Canal Royal", fr: "Joutes nautiques du canal Royal" },
    era: { en: "Since 1666", fr: "Depuis 1666" },
    summary: {
      en: "Two boats, two jousters with lances: Sète's most famous sport, right in the town centre.",
      fr: "Deux barques, deux jouteurs armés d'une lance : le sport phare de Sète, en plein centre-ville.",
    },
    description: [
      {
        en: "Each boat is rowed by a crew while a jouster stands on a raised platform at the back. As the boats pass each other, each tries to push the other into the water with his lance, protected by a wooden shield.",
        fr: "Chaque barque est menée par des rameurs, tandis qu'un jouteur se tient sur une plateforme surélevée à l'arrière. Quand les barques se croisent, chacun tente de faire tomber l'autre à l'eau avec sa lance, protégé par un pavois en bois.",
      },
      {
        en: "The first jousts in Sète were held in 1666 to celebrate the founding of the port. The great tournament takes place every August for the Saint-Louis festival.",
        fr: "Les premières joutes de Sète ont eu lieu en 1666 pour fêter la création du port. Le grand tournoi se tient chaque mois d'août pour la Saint-Louis.",
      },
    ],
    didYouKnow: {
      en: "A band of oboes and drums plays during every joust — the music is part of the sport.",
      fr: "Un orchestre de hautbois et de tambours joue pendant chaque joute : la musique fait partie du sport.",
    },
  },
  {
    id: "cite-espace",
    stationId: "87612010",
    category: "science",
    lat: 43.5866,
    lon: 1.4934,
    title: { en: "Cité de l'espace", fr: "Cité de l'espace" },
    era: { en: "1997", fr: "1997" },
    summary: {
      en: "A space science park with a life-size Ariane 5 rocket, in the capital of European aerospace.",
      fr: "Un parc consacré à l'espace, avec une fusée Ariane 5 grandeur nature, dans la capitale européenne de l'aéronautique.",
    },
    description: [
      {
        en: "Toulouse is home to the French space agency's main centre and to many satellite builders. The Cité de l'espace explains their work to the public with interactive exhibitions.",
        fr: "Toulouse accueille le principal centre de l'agence spatiale française et de nombreux constructeurs de satellites. La Cité de l'espace explique leur travail au public avec des expositions interactives.",
      },
      {
        en: "In the park stand a 53 m model of the Ariane 5 rocket and a copy of the Mir space station that visitors can walk through. A planetarium shows the night sky.",
        fr: "Dans le parc se dressent une maquette de 53 m de la fusée Ariane 5 et une réplique de la station spatiale Mir que l'on peut visiter. Un planétarium montre le ciel étoilé.",
      },
    ],
    didYouKnow: {
      en: "Inside Mir, you can see how cosmonauts slept, ate and washed in weightlessness.",
      fr: "Dans Mir, on découvre comment les cosmonautes dormaient, mangeaient et se lavaient en apesanteur.",
    },
  },
  {
    id: "four-solaire",
    stationId: "87784819",
    category: "science",
    lat: 42.4936,
    lon: 2.0353,
    title: { en: "Odeillo Solar Furnace", fr: "Four solaire d'Odeillo" },
    era: { en: "1970", fr: "1970" },
    summary: {
      en: "A giant curved mirror that concentrates sunlight to over 3,000 °C, a few minutes from the station.",
      fr: "Un miroir géant qui concentre la lumière du soleil à plus de 3 000 °C, à quelques minutes de la gare.",
    },
    description: [
      {
        en: "On the hillside, dozens of flat mirrors follow the sun and send its light onto a huge parabolic mirror built into the laboratory. It focuses all that light onto a target barely larger than a saucepan.",
        fr: "Sur la pente, des dizaines de miroirs plats suivent le soleil et renvoient sa lumière vers un immense miroir parabolique intégré au laboratoire. Celui-ci concentre toute cette lumière sur une cible à peine plus grande qu'une casserole.",
      },
      {
        en: "The CNRS uses it to test materials at extreme temperatures, for example the heat shields of spacecraft. The site was chosen for its many sunny days and clear mountain air.",
        fr: "Le CNRS l'utilise pour tester des matériaux à des températures extrêmes, comme les boucliers thermiques des engins spatiaux. Le site a été choisi pour son ensoleillement et son air pur de montagne.",
      },
    ],
    didYouKnow: {
      en: "The idea is the same as a magnifying glass burning a leaf — only the « lens » here is as tall as a building.",
      fr: "Le principe est celui de la loupe qui brûle une feuille — sauf qu'ici la « loupe » est haute comme un immeuble.",
    },
  },
  {
    id: "museum-toulouse",
    stationId: "87611301",
    category: "science",
    lat: 43.5937,
    lon: 1.4495,
    title: { en: "Muséum de Toulouse", fr: "Muséum de Toulouse" },
    era: { en: "Founded in 1796", fr: "Fondé en 1796" },
    summary: {
      en: "One of France's great natural history museums: fossils, skeletons, minerals and a botanical garden.",
      fr: "L'un des grands muséums d'histoire naturelle de France : fossiles, squelettes, minéraux et jardin botanique.",
    },
    description: [
      {
        en: "Its collections cover the history of life and of the Earth, from meteorites to dinosaurs and the first humans. The galleries are organised around big questions rather than lists of objects.",
        fr: "Ses collections retracent l'histoire de la vie et de la Terre, des météorites aux dinosaures et aux premiers humains. Les salles sont organisées autour de grandes questions plutôt que de listes d'objets.",
      },
      {
        en: "Right next door, the Henri-Gaussen botanical garden lets classes continue the visit outside.",
        fr: "Juste à côté, le jardin botanique Henri-Gaussen permet aux classes de prolonger la visite en plein air.",
      },
    ],
    didYouKnow: {
      en: "The museum reopened in 2008 after more than ten years of renovation.",
      fr: "Le muséum a rouvert en 2008, après plus de dix ans de travaux.",
    },
  },
  {
    id: "musee-millau",
    stationId: "87783001",
    category: "craft",
    lat: 44.0989,
    lon: 3.0777,
    title: { en: "Millau and Grands Causses Museum", fr: "Musée de Millau et des Grands Causses" },
    era: { en: "Gloves & pottery", fr: "Ganterie & céramique" },
    summary: {
      en: "Two Millau trades in one museum: Roman pottery and luxury leather gloves.",
      fr: "Deux savoir-faire de Millau dans un même musée : la poterie romaine et le gant de luxe.",
    },
    description: [
      {
        en: "Two thousand years ago, the workshops of La Graufesenque, just outside Millau, made red glossy pottery called terra sigillata, sold all over the Roman Empire.",
        fr: "Il y a deux mille ans, les ateliers de la Graufesenque, aux portes de Millau, fabriquaient une vaisselle rouge et brillante, la sigillée, vendue dans tout l'Empire romain.",
      },
      {
        en: "Later, Millau became the capital of glove-making, using the soft skins of lambs from the local sheep farms — the same flocks whose milk makes Roquefort cheese.",
        fr: "Plus tard, Millau est devenue la capitale du gant, grâce aux peaux souples des agneaux des élevages voisins — les mêmes troupeaux dont le lait donne le roquefort.",
      },
    ],
    didYouKnow: {
      en: "Millau gloves are still made by hand today for major fashion houses.",
      fr: "Des gants sont encore cousus à la main à Millau aujourd'hui pour de grandes maisons de mode.",
    },
  },
  {
    id: "hotel-assezat",
    stationId: "87611004",
    category: "craft",
    lat: 43.6005,
    lon: 1.4413,
    title: { en: "Hôtel d'Assézat", fr: "Hôtel d'Assézat" },
    era: { en: "1555", fr: "1555" },
    summary: {
      en: "The palace of a merchant who grew rich on pastel, the blue dye that made Toulouse wealthy.",
      fr: "Le palais d'un marchand enrichi par le pastel, la teinture bleue qui a fait la fortune de Toulouse.",
    },
    description: [
      {
        en: "In the 16th century, farmers around Toulouse grew woad, a plant whose leaves give a blue dye. Crushed and dried into balls called « cocagnes », it was exported all over Europe to dye cloth.",
        fr: "Au XVIᵉ siècle, les paysans autour de Toulouse cultivaient le pastel, une plante dont les feuilles donnent une teinture bleue. Broyées et séchées en boules appelées « coques » ou « cocagnes », elles étaient exportées dans toute l'Europe pour teindre les tissus.",
      },
      {
        en: "Pierre d'Assézat, one of the richest pastel merchants, built this Renaissance mansion. Today it houses the Fondation Bemberg's art collection.",
        fr: "Pierre d'Assézat, l'un des plus riches marchands de pastel, fit bâtir cet hôtel Renaissance. Il abrite aujourd'hui les collections d'art de la Fondation Bemberg.",
      },
    ],
    didYouKnow: {
      en: "The expression « pays de cocagne » — a land of plenty — comes from these balls of pastel.",
      fr: "L'expression « pays de cocagne » — un pays d'abondance — viendrait de ces boules de pastel.",
    },
  },
];

export const DISCOVERY_BY_ID = new Map(DISCOVERIES.map((d) => [d.id, d]));

// Lieux regroupés par gare (dans l'ordre du tableau)
export const DISCOVERIES_BY_STATION = DISCOVERIES.reduce((m, d) => {
  if (!m.has(d.stationId)) m.set(d.stationId, []);
  m.get(d.stationId)!.push(d);
  return m;
}, new Map<string, Discovery[]>());

// Distance à vol d'oiseau, en km
export function distanceKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLon = (b.lon - a.lon) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

// Temps à pied estimé : les rues font environ 30 % de plus que la ligne droite, à 4,8 km/h
export const WALK_LIMIT_KM = 3.5; // au-delà, on affiche la distance plutôt qu'un temps à pied
export const walkMinutes = (km: number) => Math.max(1, Math.round(((km * 1.3) / 4.8) * 60));
