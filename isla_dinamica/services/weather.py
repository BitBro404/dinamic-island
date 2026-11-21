"""Clima de Open-Meteo."""
from ..common import *  # noqa: F401,F403


WMO = {0: ("Despejado", "clear"), 1: ("Mayormente despejado", "clear"), 2: ("Parcialmente nublado", "few-clouds"),
       3: ("Nublado", "overcast"), 45: ("Niebla", "fog"), 48: ("Niebla", "fog"),
       51: ("Llovizna ligera", "showers-scattered"), 53: ("Llovizna", "showers-scattered"),
       55: ("Llovizna intensa", "showers"), 56: ("Llovizna helada", "showers"), 57: ("Llovizna helada", "showers"),
       61: ("Lluvia ligera", "showers-scattered"), 63: ("Lluvia", "showers"), 65: ("Lluvia fuerte", "showers"),
       66: ("Lluvia helada", "showers"), 67: ("Lluvia helada", "showers"), 71: ("Nieve ligera", "snow"),
       73: ("Nieve", "snow"), 75: ("Nieve intensa", "snow"), 77: ("Granizo", "snow"),
       80: ("Chubascos", "showers-scattered"), 81: ("Chubascos", "showers"), 82: ("Chubascos fuertes", "showers"),
       85: ("Chubascos de nieve", "snow"), 86: ("Chubascos de nieve", "snow"), 95: ("Tormenta", "storm"),
       96: ("Tormenta con granizo", "storm"), 99: ("Tormenta con granizo", "storm")}


WMO_KIND = {0: "clear", 1: "clear", 2: "partly", 3: "cloudy", 45: "fog", 48: "fog",
            51: "drizzle", 53: "drizzle", 55: "drizzle", 56: "drizzle", 57: "drizzle",
            61: "rain", 63: "rain", 65: "heavy-rain", 66: "rain", 67: "heavy-rain",
            80: "rain", 81: "rain", 82: "heavy-rain",
            71: "snow", 73: "snow", 75: "snow", 77: "snow", 85: "snow", 86: "snow",
            95: "storm", 96: "storm", 99: "storm"}


RAINY = ("drizzle", "rain", "heavy-rain", "storm")


def weather_kind(code, day=True):
    k = WMO_KIND.get(code, "cloudy")
    if not day and k in ("clear", "partly"):
        k += "-night"
    return k


def weather_icon(code, day=True):
    kind = WMO.get(code, ("", "overcast"))[1]
    if not day and kind in ("clear", "few-clouds"):
        kind += "-night"
    return f"weather-{kind}-symbolic"


class Weather:
    """Clima de Open-Meteo (gratis, sin cuenta). Se actualiza cada 20 minutos."""

    def __init__(self, config, on_change):
        self.cfg, self.on_change = config, on_change
        self.data, self.place, self.error, self.loading = None, None, None, False
        self._retry = None
        self.refresh()
        GLib.timeout_add_seconds(1200, lambda: (self.refresh(), True)[1])

    @property
    def city(self):
        return self.cfg.data.get("city") or tz_city()

    def set_city(self, name):
        self.cfg.data["city"] = name.strip() or None
        self.cfg.save()
        self.place = None
        self.refresh()

    def refresh(self):
        if self.loading or not self.cfg.data["features"].get("weather", True):
            return
        self.loading = True
        self.on_change()
        city, place = self.city, self.place

        def work():
            try:
                if place is None or place["query"] != city:
                    g = fetch_json("https://geocoding-api.open-meteo.com/v1/search?count=1&language=es&name="
                                   + urllib.parse.quote(city))
                    res = (g.get("results") or [None])[0]
                    if not res:
                        raise LookupError(f"No encontré «{city}»")
                    pl = {"query": city, "name": res["name"], "lat": res["latitude"], "lon": res["longitude"]}
                else:
                    pl = place
                w = fetch_json(
                    f"https://api.open-meteo.com/v1/forecast?latitude={pl['lat']}&longitude={pl['lon']}"
                    "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,"
                    "wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,precipitation,uv_index"
                    "&hourly=temperature_2m,weather_code,is_day,precipitation_probability"
                    "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                    "precipitation_sum,sunrise,sunset,uv_index_max"
                    "&timezone=auto&forecast_days=7")
                GLib.idle_add(self._done, pl, w, None)
            except LookupError as e:
                GLib.idle_add(self._done, None, None, str(e))
            except Exception:
                GLib.idle_add(self._done, None, None, "Sin conexión con el servicio del clima")

        threading.Thread(target=work, daemon=True).start()

    def _retry_now(self):
        self._retry = None
        self.refresh()
        return False

    def _done(self, place, w, err):
        self.loading = False
        if err:
            self.error = err
            if not self._retry:      # la red falla a ratos: reintentar en un minuto, no en 20
                self._retry = GLib.timeout_add_seconds(60, self._retry_now)
        else:
            cur, daily, hourly = w["current"], w["daily"], w["hourly"]
            now_h = cur["time"][:13]
            idx = next((i for i, t in enumerate(hourly["time"]) if t[:13] > now_h), 0)
            pops = hourly.get("precipitation_probability") or [None] * len(hourly["time"])
            hours = [{"hour": hourly["time"][i][11:16], "temp": hourly["temperature_2m"][i],
                      "icon": weather_icon(hourly["weather_code"][i], hourly["is_day"][i]),
                      "kind": weather_kind(hourly["weather_code"][i], hourly["is_day"][i]),
                      "pop": pops[i]}
                     for i in range(idx, min(idx + 24, len(hourly["time"])))]
            names = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
            days = []
            for i, day in enumerate(daily["time"]):
                wd = time.strptime(day, "%Y-%m-%d").tm_wday
                days.append({"name": "Hoy" if i == 0 else "Mañana" if i == 1 else names[wd],
                             "kind": weather_kind(daily["weather_code"][i]),
                             "max": daily["temperature_2m_max"][i], "min": daily["temperature_2m_min"][i],
                             "pop": daily["precipitation_probability_max"][i]})
            # ¿lluvia o tormenta en las próximas 3 horas?
            kind_now = weather_kind(cur["weather_code"], cur["is_day"])
            soon = None
            if kind_now not in RAINY:
                soon = next((h for h in hours[:3] if h["kind"] in RAINY and (h["pop"] or 0) >= 50), None)
            self.place, self.error = place, None
            self.data = {"temp": cur["temperature_2m"], "feels": cur["apparent_temperature"],
                         "humidity": cur["relative_humidity_2m"], "wind": cur["wind_speed_10m"],
                         "code": cur["weather_code"], "day": bool(cur["is_day"]),
                         "desc": WMO.get(cur["weather_code"], ("—", ""))[0],
                         "icon": weather_icon(cur["weather_code"], cur["is_day"]),
                         "max": daily["temperature_2m_max"][0], "min": daily["temperature_2m_min"][0],
                         "rain": (daily.get("precipitation_probability_max") or [None])[0],
                         "kind": kind_now, "hours": hours, "days": days, "soon": soon,
                         "wind_dir": cur.get("wind_direction_10m"), "gusts": cur.get("wind_gusts_10m"),
                         "clouds": cur.get("cloud_cover"), "uv": cur.get("uv_index"),
                         "rain_mm": daily["precipitation_sum"][0], "uv_max": daily["uv_index_max"][0],
                         "sunrise": daily["sunrise"][0][11:16], "sunset": daily["sunset"][0][11:16],
                         "updated": time.time()}
        self.on_change()
        return False
