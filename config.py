# =====================================================================
#  LE TUE PREFERENZE — modifica liberamente questo file
#  (le maiuscole/minuscole non contano)
# =====================================================================

# Una posizione viene segnalata se il TITOLO contiene almeno una di queste parole.
TITLE_KEYWORDS = [
    # Product / Program management
    "product manager",
    "program manager",
    "programme manager",
    "project manager",
    "product operations",
    "product specialist",
    # Business / Sales / Marketing
    "marketing",
    "sales",
    "account manager",
    "account executive",
    "account strategist",
    "business development",
    "partner manager",
    "partnership",
    "go-to-market",
    "gtm",
    "growth",
    "customer success",
    "business analyst",
    "strategy",
]

# ...ma viene SCARTATA se il titolo contiene una di queste parole.
# (hai scelto Junior + Mid/Senior: escludo stage e ruoli dirigenziali)
TITLE_EXCLUDE = [
    "intern",
    "internship",
    "apprentice",
    "director",
    "vice president",
    "vp,",
    "vp ",
    "head of",
    "distinguished",
    "engineer",          # niente ruoli puramente tecnici
    "engineering manager",
]

# Paesi in cui deve trovarsi la posizione.
# Ogni voce: nome mostrato -> nomi/città con cui compare sui siti.
# Le sigle di 2 lettere (es. "it") sono codici paese ISO, usati solo dove
# il sito li fornisce in modo strutturato.
COUNTRIES = {
    "Italy": ["italy", "it", "milan", "rome"],
    "Ireland": ["ireland", "ie", "dublin"],
    "United Kingdom": ["united kingdom", "uk", "gb", "london", "manchester", "edinburgh"],
    "Germany": ["germany", "de", "munich", "berlin", "hamburg", "frankfurt"],
    "France": ["france", "fr", "paris"],
    "Spain": ["spain", "es", "madrid", "barcelona"],
    "Netherlands": ["netherlands", "nl", "amsterdam"],
    "Switzerland": ["switzerland", "ch", "zurich", "zürich", "geneva"],
    "Belgium": ["belgium", "be", "brussels"],
    "Sweden": ["sweden", "se", "stockholm"],
    "Denmark": ["denmark", "dk", "copenhagen"],
    "Norway": ["norway", "no", "oslo"],
    "Finland": ["finland", "fi", "helsinki"],
    "Poland": ["poland", "pl", "warsaw"],
    "Portugal": ["portugal", "pt", "lisbon"],
    "Austria": ["austria", "at", "vienna"],
    "Czech Republic": ["czech", "czechia", "cz", "prague"],
    "Greece": ["greece", "gr", "athens"],
}

# Al primo avvio: True = ti mando una mail con TUTTE le posizioni già aperte
# che corrispondono ai filtri; False = registro solo quelle esistenti e ti
# avviso solo delle nuove da lì in poi.
SEND_INITIAL_DIGEST = True
