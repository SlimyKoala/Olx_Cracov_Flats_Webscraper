from bs4 import BeautifulSoup
import requests
import pandas as pd
import matplotlib.pyplot as plt

import folium
import geopandas as gpd
import webbrowser

geopandas_to_olx_names_dict = {
    "Dzielnica VII Zwierzyniec": "Zwierzyniec",
    "Dzielnica X Swoszowice": "Swoszowice",
    "Dzielnica VIII Dębniki": "Dębniki",
    "Dzielnica XII Biezanow-Prokocim": "Bieżanów-Prokocim",
    "Dzielnica XIII Podgórze": "Podgórze",
    "Dzielnica XVIII Nowa Huta": "Nowa Huta",
    "Dzielnica XVI Bieńczyce": "Bieńczyce",
    "Dzielnica IX Łagiewniki-Borek Fałęcki": "Łagiewniki-Borek Fałęcki",
    "Dzielnica I Stare Miasto": "Stare Miasto",
    "Dzielnica II Grzegórzki": "Grzegórzki",
    "Dzielnica III Prądnik Czerwony": "Prądnik Czerwony",
    "Dzielnica IV Prądnik Biały": "Prądnik Biały",
    "Dzielnica V Krowodrza": "Krowodrza",
    "Dzielnica VI Bronowice": "Bronowice",
    "Dzielnica XI Podgórze Duchackie": "Podgórze Duchackie",
    "Dzielnica XIV Czyżyny": "Czyżyny",
    "Dzielnica XV Mistrzejowice": "Mistrzejowice",
    "Dzielnica XVII Wzgórza Krzeszławickie": "Wzgórza Krzesławickie",
}
map_name = "mapa_oferty_kraków_test.html"

BASE_URL = "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/krakow/"

CSS_TITLE_STYLE = "font-size:18px; color:white; text-shadow: 2px 2px 0px #000000"

data = []


def scrape(pages : int):
    for i in range(1, pages):
        response = requests.get(f"{BASE_URL}?page={i}")

        soup = BeautifulSoup(response.text, "html.parser")

        offers = soup.find_all("div", class_="css-1sw7q4x")

        for offer in offers:

            title = offer.find("h4", class_="css-hzlye5")
            price = offer.find("p", class_="css-blr5zl")
            link = offer.find("a")
            area = offer.find("span", class_="css-h59g4b")
            region = offer.find("p", class_="css-1b24pxk")

            try:
                data_row = {
                    "Tytuł": title.text,
                    "Cena": price.text,
                    "link": link["href"] if link["href"].startswith("https") else "https://www.olx.pl" + link["href"],
                    "Metraż": area.text.split(" ")[0],
                    "Dzielnica": region.text.strip().split(" - ")[0].split(", ")[1]
                }

                data.append(data_row)
            except:
                pass
        print(f"Strona {i} zakończona")

    return pd.DataFrame(data)

def edit_dataframe(df_to_edit):
    df_to_edit["Cena"] = (
        df_to_edit["Cena"]
        .str.replace("zł", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.extract(r"(\d+)")
        .astype(float)
    )
    df_to_edit["Metraż"] = pd.to_numeric(df_to_edit["Metraż"].str.replace(",", "."), errors="coerce")
    df_to_edit["Cena_m2"] = df_to_edit["Cena"] / df_to_edit["Metraż"]

def group_and_aggregate_dataframe(df_to_group):
    df_to_group = df_to_group.groupby("Dzielnica").agg({
        "Tytuł": lambda x: list(x),
        "link": lambda x: list(x),
        "Cena_m2": "mean"
    }).rename(columns={"Cena_m2": "Średnia cena/m²"})
    df_to_group["Liczba ofert"] = df_to_group["Tytuł"].apply(len)
    df_to_group = df_to_group.reset_index()

    return df_to_group

def generate_geodata(offers_data: pd.DataFrame):
    result_geodata = gpd.read_file("krakow-dzielnice.geojson")
    result_geodata["name"] = result_geodata["name"].map(geopandas_to_olx_names_dict)
    result_geodata = result_geodata.merge(offers_data, left_on="name", right_on="Dzielnica", how="left")
    result_geodata["Liczba ofert"] = result_geodata["Liczba ofert"].fillna(0)

    return result_geodata

def generate_map(map_data):
    global centroid
    m = folium.Map(location=[50.0614, 19.9366], zoom_start=12, zoom_control=True)
    choropleth_oferty = folium.Choropleth(
        geo_data=map_data,
        data=map_data,
        columns=["name", "Liczba ofert"],
        key_on="feature.properties.name",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Liczba ofert",
        name="Liczba ofert"  # <<< NAZWA WARSTWY
    ).add_to(m)
    for _, row in map_data.iterrows():
        centroid = row["geometry"].centroid
        if pd.notnull(row["Liczba ofert"]) and row["Liczba ofert"] > 0:

            tytuly = row["Tytuł"][:5]
            linki = row["link"][:5]

            # łączymy w klikalne odnośniki HTML
            oferty_html = "<br>".join(
                [f'<a href="{l}" target="_blank">{t}</a>' for t, l in zip(tytuly, linki)]
            )

            popup_html = f"""
            <b>{row['name']}</b><br>
            Liczba ofert: {int(row['Liczba ofert'])}<br>
            Średnia cena za m²: {row['Średnia cena/m²']:.0f} zł<br>
            <br>
            <u>Przykładowe mieszkania:</u><br>
            {oferty_html}
            """
        else:
            popup_html = f"<b>{row['name']}</b><br>Brak ofert"

        folium.Marker(
            [centroid.y, centroid.x],
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m)
        folium.map.Marker(
            [centroid.y, centroid.x],
            icon=folium.DivIcon(
                html=f"<div style='{CSS_TITLE_STYLE}'>{row['name']}</div>",
                icon_anchor=(-30, 60),
                icon_size=(50, 50)
            )
        ).add_to(m)
    choropleth_cena = folium.Choropleth(
        geo_data=map_data,
        data=map_data,
        columns=["name", "Średnia cena/m²"],
        key_on="feature.properties.name",
        fill_color="PuBuGn",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Średnia cena za m²",
        name="Średnia cena za m²"  # <<< NAZWA WARSTWY
    ).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(map_name)



df = scrape(5)
df.to_csv("mieszkania_krakow.csv", index=False, encoding="utf-8")

edit_dataframe(df)

grouped_olx_data = group_and_aggregate_dataframe(df)
regions_geodata = generate_geodata(grouped_olx_data)


generate_map(regions_geodata)
webbrowser.open(map_name)
print("kod zakończony")