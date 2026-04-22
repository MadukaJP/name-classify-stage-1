import pycountry

def get_country_name_from_id(country_id: str):
    if not country_id:
        return None
    
    try:
        country = pycountry.countries.get(alpha_2=country_id.upper())
        
        return country.name if country else None
    except (LookupError, AttributeError):
        return None