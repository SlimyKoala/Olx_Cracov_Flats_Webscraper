from bs4 import BeautifulSoup
import requests
import pandas as pd
import matplotlib.pyplot as plt

import folium
import geopandas as gpd

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

BASE_URL = "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/krakow/"

data = []

# for i in range(1, 26):
for i in range(1, 2):
    response = requests.get(f"{BASE_URL}?page={i}")

    soup = BeautifulSoup(response.text, "html.parser")

    offers = soup.find_all("div", class_="css-1sw7q4x")

    for offer in offers:

        title = offer.find("h4", class_="css-hzlye5")
        price = offer.find("p", class_= "css-blr5zl")
        link = offer.find("a")
        area = offer.find("span", class_="css-h59g4b")
        region = offer.find("p", class_="css-1b24pxk")

        print("--------------------------------------------------")
        try:
            data_row = {
                "Tytuł": title.text,
                "Cena": price.text,
                "link": link["href"],
                "Metraż": area.text.split(" ")[0],
                "Dzielnica": region.text.strip().split(" - ")[0].split(", ")[1]
            }

            data.append(data_row)
        except:
            pass
df = pd.DataFrame(data)

df.to_csv("mieszkania_krakow.csv", index=False, encoding="utf-8")

df["Cena"] = (
    df["Cena"]
    .str.replace("zł", "", regex=False)
    .str.replace(" ", "", regex=False)
    .str.extract(r"(\d+)")
    .astype(float)
)


# plt.hist(df["Cena"].dropna(), bins=30)
# plt.xlabel("Cena mieszkania w mln złotych")
# plt.ylabel("Liczba ofert w danym przedziale")
# plt.title("Rozkład cen mieszkań w Krakowie")
# plt.show()

m = folium.Map(location=[50.0614, 19.9366], zoom_start=12, zoom_control=True)

df["Metraż"] = pd.to_numeric(df["Metraż"].str.replace(",", "."), errors="coerce")
df["Cena_m2"] = df["Cena"] / df["Metraż"]

grouped_olx_data = df.groupby("Dzielnica").agg({
    "Tytuł": lambda x: list(x),
    "Cena_m2": "mean"
}).rename(columns={"Cena_m2": "Średnia cena/m²"})

grouped_olx_data["Liczba ofert"] = grouped_olx_data["Tytuł"].apply(len)
grouped_olx_data = grouped_olx_data.reset_index()

regions_geodata = gpd.read_file("krakow-dzielnice.geojson")
regions_geodata["name"] = regions_geodata["name"].map(geopandas_to_olx_names_dict)


regions_geodata = regions_geodata.merge(grouped_olx_data, left_on="name", right_on="Dzielnica", how="left")
regions_geodata["Liczba ofert"] = regions_geodata["Liczba ofert"].fillna(0)


choropleth_oferty = folium.Choropleth(
    geo_data=regions_geodata,
    data=regions_geodata,
    columns=["name", "Liczba ofert"],
    key_on="feature.properties.name",
    fill_color="YlOrRd",
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name="Liczba ofert",
    name="Liczba ofert"   # <<< NAZWA WARSTWY
).add_to(m)

for _, row in regions_geodata.iterrows():
    centroid = row["geometry"].centroid
    if pd.notnull(row["Liczba ofert"]) and row["Liczba ofert"] > 0:
        tytuly = "<br>".join(row["Tytuł"][:5])  # max 5 tytułów na popup
        popup_html = f"""
            <b>{row['name']}</b><br>
            Liczba ofert: {int(row['Liczba ofert'])}<br>
            Średnia cena za m²: {row['Średnia cena/m²']:.0f} zł<br>
            <br>
            <u>Przykładowe mieszkania:</u><br>
            {tytuly}
            """
    else:
        popup_html = f"<b>{row['name']}</b><br>Brak ofert"

    folium.Marker(
        [centroid.y, centroid.x],
        popup=folium.Popup(popup_html, max_width=300)
    ).add_to(m)

choropleth_cena = folium.Choropleth(
    geo_data=regions_geodata,
    data=regions_geodata,
    columns=["name", "Średnia cena/m²"],
    key_on="feature.properties.name",
    fill_color="PuBuGn",
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name="Średnia cena za m²",
    name="Średnia cena za m²"   # <<< NAZWA WARSTWY
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

m.save("mapa_oferty_kraków_test.html")