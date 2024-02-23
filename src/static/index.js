// Initialize and add the map
let map;

async function initMap(input_lat, input_long) {
  // The location of Uluru
  const position = { lat: input_lat , lng: input_long };
  // Request needed libraries.
  //@ts-ignore
  const { Map } = await google.maps.importLibrary("maps");
  const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
    map = new Map(document.getElementById("map"), {
    zoom: 10,
    center: position,
    mapId: "Athlete Position",
  });

}

async function addMarker(input_lat, input_long, marker_label) {
  const position = {lat: input_lat, lng: input_long};

  const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");

  const marker = new AdvancedMarkerElement({
    map: map,
    position: position,
    title: marker_label,

  });
}