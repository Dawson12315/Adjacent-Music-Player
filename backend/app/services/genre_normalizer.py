def normalize_genre(value):
    if not value:
        return None

    cleaned = value.strip()

    if not cleaned:
        return None

    lowered = cleaned.lower()

    aliases = {
        "pop": "Pop",
        "rock": "Rock",
        "rap": "Rap",
        "hip hop": "Hip-Hop",
        "hip-hop": "Hip-Hop",
        "r&b": "R&B",
        "rnb": "R&B",
        "edm": "EDM",
        "dance": "Dance",
        "house": "House",
        "trap": "Trap",
        "alternetive": "Alternative",
        "ambient": "Ambient",
        "synthpop": "Synthpop",
        "synthwave": "Synthwave",
        "gospel": "Gospel",
        "ballad": "Ballad",
        "jazz": "Jazz",
        "soul": "Soul",
        "indie": "Indie",
        "alternative": "Alternative",
        "electro": "Electro",
        "electropop": "Electropop",

        "electro house": "Electro House",
        "electro-house": "Electro House",

        "dance-pop": "Dance-Pop",
        "dance pop": "Dance-Pop",

        "pop-soul": "Pop-Soul",
        "pop soul": "Pop-Soul",

        "quiet storm": "Quiet Storm",
        "quiet-storm": "Quiet Storm",

        "new jack swing": "New Jack Swing",
        "new-jack-swing": "New Jack Swing",

        "drum and bass": "Drum and Bass",
        "drum-and-bass": "Drum and Bass",
        "dnb": "Drum and Bass",
        "d&b": "Drum and Bass",

        "ukg": "UKG",
        "garage": "Garage",

        "uk garage": "UK Garage",
        "uk-garage": "UK Garage",

        "2-step": "2-Step",

        "future garage": "Future Garage",
        "future-garage": "Future Garage",

        "grime": "Grime",
        "dubstep": "Dubstep",
        "brostep": "Brostep",
        "chillstep": "Chillstep",

        "melodic dubstep": "Melodic Dubstep",
        "melodic-dubstep": "Melodic Dubstep",

        "future bass": "Future Bass",
        "future-bass": "Future Bass",

        "bass": "Bass",

        "bass music": "Bass Music",
        "bass-music": "Bass Music",

        "trap edm": "Trap EDM",
        "trap-edm": "Trap EDM",

        "hardstyle": "Hardstyle",
        "hardcore": "Hardcore",

        "happy hardcore": "Happy Hardcore",
        "happy-hardcore": "Happy Hardcore",

        "gabber": "Gabber",
        "techno": "Techno",

        "minimal techno": "Minimal Techno",
        "minimal-techno": "Minimal Techno",

        "melodic techno": "Melodic Techno",
        "melodic-techno": "Melodic Techno",

        "deep techno": "Deep Techno",
        "deep-techno": "Deep Techno",

        "acid techno": "Acid Techno",
        "acid-techno": "Acid Techno",

        "trance": "Trance",

        "progressive trance": "Progressive Trance",
        "progressive-trance": "Progressive Trance",

        "uplifting trance": "Uplifting Trance",
        "uplifting-trance": "Uplifting Trance",

        "psytrance": "Psytrance",

        "goa trance": "Goa Trance",
        "goa-trance": "Goa Trance",

        "hard trance": "Hard Trance",
        "hard-trance": "Hard Trance",

        "progressive house": "Progressive House",
        "progressive-house": "Progressive House",

        "deep house": "Deep House",
        "deep-house": "Deep House",

        "tropical house": "Tropical House",
        "tropical-house": "Tropical House",

        "tech house": "Tech House",
        "tech-house": "Tech House",

        "future house": "Future House",
        "future-house": "Future House",

        "big room": "Big Room",
        "big-room": "Big Room",

        "big room house": "Big Room House",
        "big-room-house": "Big Room House",

        "funky house": "Funky House",
        "funky-house": "Funky House",

        "disco house": "Disco House",
        "disco-house": "Disco House",

        "nu disco": "Nu Disco",
        "nu-disco": "Nu Disco",

        "disco": "Disco",

        "italo disco": "Italo Disco",
        "italo-disco": "Italo Disco",

        "boogie": "Boogie",
        "funk": "Funk",
        "p-funk": "P-Funk",

        "neo soul": "Neo-Soul",
        "neo-soul": "Neo-Soul",

        "contemporary r&b": "Contemporary R&B",
        "contemporary-r&b": "Contemporary R&B",

        "smooth jazz": "Smooth Jazz",
        "smooth-jazz": "Smooth Jazz",

        "bebop": "Bebop",

        "hard bop": "Hard Bop",
        "hard-bop": "Hard Bop",

        "cool jazz": "Cool Jazz",
        "cool-jazz": "Cool Jazz",

        "free jazz": "Free Jazz",
        "free-jazz": "Free Jazz",

        "fusion": "Fusion",

        "jazz fusion": "Jazz Fusion",
        "jazz-fusion": "Jazz Fusion",

        "latin jazz": "Latin Jazz",
        "latin-jazz": "Latin Jazz",

        "swing": "Swing",

        "big band": "Big Band",
        "big-band": "Big Band",

        "blues": "Blues",

        "delta blues": "Delta Blues",
        "delta-blues": "Delta Blues",

        "chicago blues": "Chicago Blues",
        "chicago-blues": "Chicago Blues",

        "electric blues": "Electric Blues",
        "electric-blues": "Electric Blues",

        "acoustic blues": "Acoustic Blues",
        "acoustic-blues": "Acoustic Blues",

        "country": "Country",
        "alt-country": "Alt-Country",

        "country rock": "Country Rock",
        "country-rock": "Country Rock",

        "outlaw country": "Outlaw Country",
        "outlaw-country": "Outlaw Country",

        "bluegrass": "Bluegrass",
        "americana": "Americana",
        "folk": "Folk",

        "folk rock": "Folk Rock",
        "folk-rock": "Folk Rock",

        "indie folk": "Indie Folk",
        "indie-folk": "Indie Folk",

        "contemporary folk": "Contemporary Folk",
        "contemporary-folk": "Contemporary Folk",

        "celtic": "Celtic",

        "celtic folk": "Celtic Folk",
        "celtic-folk": "Celtic Folk",

        "world": "World",

        "world music": "World Music",
        "world-music": "World Music",

        "afrobeat": "Afrobeat",
        "afrobeats": "Afrobeats",
        "afropop": "Afropop",
        "latin": "Latin",

        "latin pop": "Latin Pop",
        "latin-pop": "Latin Pop",

        "reggaeton": "Reggaeton",

        "latin trap": "Latin Trap",
        "latin-trap": "Latin Trap",

        "salsa": "Salsa",
        "bachata": "Bachata",
        "merengue": "Merengue",
        "cumbia": "Cumbia",

        "bossa nova": "Bossa Nova",
        "bossa-nova": "Bossa Nova",

        "samba": "Samba",
        "tango": "Tango",
        "flamenco": "Flamenco",

        "k-pop": "K-Pop",
        "j-pop": "J-Pop",
        "c-pop": "C-Pop",
        "mandopop": "Mandopop",
        "cantopop": "Cantopop",
        "j-rock": "J-Rock",
        "k-rock": "K-Rock",

        "anime": "Anime",
        "anisong": "Anisong",
        "vocaloid": "Vocaloid",

        "city pop": "City Pop",
        "city-pop": "City Pop",

        "industrial": "Industrial",

        "industrial rock": "Industrial Rock",
        "industrial-rock": "Industrial Rock",

        "industrial metal": "Industrial Metal",
        "industrial-metal": "Industrial Metal",

        "ebm": "EBM",
        "electronic body music": "EBM",
        "electronic-body-music": "EBM",

        "darkwave": "Darkwave",
        "post-punk": "Post-Punk",
        "goth": "Goth",

        "goth rock": "Goth Rock",
        "goth-rock": "Goth Rock",

        "shoegaze": "Shoegaze",

        "dream pop": "Dream Pop",
        "dream-pop": "Dream Pop",

        "noise": "Noise",
        "experimental": "Experimental",
        "avant-garde": "Avant-Garde",
        "idm": "IDM",
        "intelligent dance music": "IDM",
        "intelligent-dance-music": "IDM",
        "breakcore": "Breakcore",
        "drill": "Drill",

        "uk drill": "UK Drill",
        "uk-drill": "UK Drill",

        "indie": "Indie",

        "chicago drill": "Chicago Drill",
        "chicago-drill": "Chicago Drill",

        "trap soul": "Trap Soul",
        "trap-soul": "Trap Soul",

        "emo rap": "Emo Rap",
        "emo-rap": "Emo Rap",

        "cloud rap": "Cloud Rap",
        "cloud-rap": "Cloud Rap",

        "phonk": "Phonk",
        "lo-fi": "Lo-Fi",

        "lofi hip hop": "Lo-Fi Hip-Hop",
        "lofi-hip-hop": "Lo-Fi Hip-Hop",

        "chillhop": "Chillhop",

        "chill": "Chill",

        "lofi": "Lo-fi",
        "lo-fi": "Lo-fi",

        "boom bap": "Boom Bap",
        "boom-bap": "Boom Bap",

        "east coast hip hop": "East Coast Hip-Hop",
        "east-coast-hip-hop": "East Coast Hip-Hop",

        "west coast hip hop": "West Coast Hip-Hop",
        "west-coast-hip-hop": "West Coast Hip-Hop",

        "southern hip hop": "Southern Hip-Hop",
        "southern-hip-hop": "Southern Hip-Hop",

        "gangsta rap": "Gangsta Rap",
        "gangsta-rap": "Gangsta Rap",

        "conscious hip hop": "Conscious Hip-Hop",
        "conscious-hip-hop": "Conscious Hip-Hop",

        "alternative hip hop": "Alternative Hip-Hop",
        "alternative-hip-hop": "Alternative Hip-Hop",

        "underground hip hop": "Underground Hip-Hop",
        "underground-hip-hop": "Underground Hip-Hop",

        "hardcore hip hop": "Hardcore Hip-Hop",
        "hardcore-hip-hop": "Hardcore Hip-Hop",

        "hyperpop": "Hyperpop",
        "dancehall": "Dancehall",
        "reggae": "Reggae",
        "dub": "Dub",
        "ska": "Ska",
        "punk": "Punk",

        "punk rock": "Punk Rock",
        "punk-rock": "Punk Rock",

        "hardcore punk": "Hardcore Punk",
        "hardcore-punk": "Hardcore Punk",

        "post-hardcore": "Post-Hardcore",
        "emo": "Emo",

        "pop punk": "Pop Punk",
        "pop-punk": "Pop Punk",

        "garage rock": "Garage Rock",
        "garage-rock": "Garage Rock",

        "indie rock": "Indie Rock",
        "indie-rock": "Indie Rock",

        "alternative rock": "Alternative Rock",
        "alternative-rock": "Alternative Rock",

        "grunge": "Grunge",

        "psychedelic rock": "Psychedelic Rock",
        "psychedelic-rock": "Psychedelic Rock",

        "progressive rock": "Progressive Rock",
        "progressive-rock": "Progressive Rock",

        "math rock": "Math Rock",
        "math-rock": "Math Rock",

        "hard rock": "Hard Rock",
        "hard-rock": "Hard Rock",

        "metal": "Metal",

        "heavy metal": "Heavy Metal",
        "heavy-metal": "Heavy Metal",

        "thrash metal": "Thrash Metal",
        "thrash-metal": "Thrash Metal",

        "death metal": "Death Metal",
        "death-metal": "Death Metal",

        "black metal": "Black Metal",
        "black-metal": "Black Metal",

        "metalcore": "Metalcore",
        "deathcore": "Deathcore",

        "progressive metal": "Progressive Metal",
        "progressive-metal": "Progressive Metal",

        "nu metal": "Nu Metal",
        "nu-metal": "Nu Metal",

        "power metal": "Power Metal",
        "power-metal": "Power Metal",

        "symphonic metal": "Symphonic Metal",
        "symphonic-metal": "Symphonic Metal",

        "classical": "Classical",
        "baroque": "Baroque",

        "modern classical": "Modern Classical",
        "modern-classical": "Modern Classical",

        "opera": "Opera",
        "orchestral": "Orchestral",
        "soundtrack": "Soundtrack",

        "film score": "Film Score",
        "film-score": "Film Score",

        "video game music": "Video Game Music",
        "video-game-music": "Video Game Music",

        "vaporwave": "Vaporwave",

        "future funk": "Future Funk",
        "future-funk": "Future Funk",

        "chiptune": "Chiptune",

        "new age": "New Age",
        "new-age": "New Age",

        "meditation": "Meditation",

        "spoken word": "Spoken Word",
        "spoken-word": "Spoken Word",

        "instrumental": "Instrumental",
        "acoustic": "Acoustic",
        "piano": "Piano",
        "guitar": "Guitar",
        "remix": "Remix",
        "live": "Live",

        "indie pop": "Indie Pop",
        "indie-pop": "Indie Pop",

        "alt pop": "Alt Pop",
        "alt-pop": "Alt Pop",

        "dark pop": "Dark Pop",
        "dark-pop": "Dark Pop",

        "art pop": "Art Pop",
        "art-pop": "Art Pop",

        "pop rock": "Pop Rock",
        "pop-rock": "Pop Rock",

        "teen pop": "Teen Pop",
        "teen-pop": "Teen Pop",

        "bubblegum pop": "Bubblegum Pop",
        "bubblegum-pop": "Bubblegum Pop",

        "europop": "Europop",
        "Euro Pop": "Europop",
        "Euro-Pop": "Europop",

        "bedroom pop": "Bedroom Pop",
        "bedroom-pop": "Bedroom Pop",

        "trip hop": "Trip-Hop",
        "trip-hop": "Trip-Hop",

        "downtempo": "Downtempo",
        "chillout": "Chillout",
        "lounge": "Lounge",

        "easy listening": "Easy Listening",
        "easy-listening": "Easy Listening",

        "adult contemporary": "Adult Contemporary",
        "adult-contemporary": "Adult Contemporary",

        "roots reggae": "Roots Reggae",
        "roots-reggae": "Roots Reggae",

        "soft pop": "Soft Pop",
        "soft-pop": "Soft Pop",

        "acid jazz": "Acid Jazz",
        "acid-jazz": "Acid Jazz",

        "future jazz": "Future Jazz",
        "future-jazz": "Future Jazz",

        "blue-eyed soul": "Blue-Eyed Soul",
        "blue-eyed-soul": "Blue-Eyed Soul",

        "baroque pop": "Baroque Pop",
        "baroque-pop": "Baroque Pop",

        "glam rock": "Glam Rock",
        "glam-rock": "Glam Rock",

        "glam metal": "Glam Metal",
        "glam-metal": "Glam Metal",

        "lo-fi rock": "Lo-Fi Rock",
        "lo-fi-rock": "Lo-Fi Rock",

        "surf rock": "Surf Rock",
        "surf-rock": "Surf Rock",

        "surf pop": "Surf Pop",
        "surf-pop": "Surf Pop",

        "film music": "Film Music",
        "film-music": "Film Music",

        "orchestral pop": "Orchestral Pop",
        "orchestral-pop": "Orchestral Pop",

        "epic music": "Epic Music",
        "epic-music": "Epic Music",

        "dark ambient": "Dark Ambient",
        "dark-ambient": "Dark Ambient",

        "space ambient": "Space Ambient",
        "space-ambient": "Space Ambient",

        "ambient techno": "Ambient Techno",
        "ambient-techno": "Ambient Techno",

        "ambient house": "Ambient House",
        "ambient-house": "Ambient House",

        "hard dance": "Hard Dance",
        "hard-dance": "Hard Dance",

        "big beat": "Big Beat",
        "big-beat": "Big Beat",

        "afro house": "Afro House",
        "afro-house": "Afro House",

        "melodic house": "Melodic House",
        "melodic-house": "Melodic House",

        "world fusion": "World Fusion",
        "world-fusion": "World Fusion",

        "tropical bass": "Tropical Bass",
        "tropical-bass": "Tropical Bass",

        "jazz pop": "Jazz Pop",
        "jazz-pop": "Jazz Pop",

        "alt rock": "Alt Rock",
        "alt-rock": "Alt Rock",

        "reggae pop": "Reggae Pop",
        "reggae-pop": "Reggae Pop",

        "alternative pop": "Alternative Pop",
        "alternative-pop": "Alternative Pop"
    }

    if lowered in aliases:
        return aliases[lowered]
    return cleaned.title()