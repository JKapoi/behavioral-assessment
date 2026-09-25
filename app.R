shiny::runApp("C:/Users/ADMIN/Documents/shiny_polio_app")


#===============================================================================
# SHINY APP: POLIO VIRUS HEATMAP & CLUSTER MAP WITH FILTERS + PNG EXPORT
#===============================================================================

library(shiny)
library(readxl)
library(dplyr)
library(sf)
library(mapgl)
library(viridisLite)
library(webshot2)
library(htmlwidgets)

Sys.setenv(MAPTILER_API_KEY = "hxrAw46qpobL63GesyZb")

ui <- fluidPage(
  titlePanel("\U0001F4CD Polio Virus Heatmap & Clustering"),
  sidebarLayout(
    sidebarPanel(
      selectInput("year", "Select Year:", choices = NULL, selected = NULL),
      selectInput("country", "Select Country:", choices = NULL, selected = NULL),
      selectInput("virus", "Select Virus Type:", choices = NULL, selected = NULL),
      selectInput("emergence", "Select Emergence Group:", choices = NULL, selected = NULL),
      downloadButton("download_heatmap", "Download Heatmap (PNG)")
    ),
    mainPanel(
      tabsetPanel(
        tabPanel("Heatmap", maplibreOutput("heatmap")),
        tabPanel("Cluster Map", maplibreOutput("clustermap"))
      )
    )
  )
)

server <- function(input, output, session) {
  
  raw_data <- read_excel(
    path = "C:/Users/ADMIN/Documents/AAAPEPVirus/AScript/AllPolioviruses_20230406_V2.xlsx",
    sheet = "AllPolioviruses_20230303"
  ) |> 
    rename(latitude = Lat, longitude = Long) |> 
    filter(!is.na(latitude) & !is.na(longitude)) |> 
    filter(between(latitude, -35, 38), between(longitude, -20, 55))
  
  updateSelectInput(session, "year", choices = c("All", sort(unique(raw_data$Year))), selected = "All")
  updateSelectInput(session, "country", choices = c("All", sort(unique(raw_data$Country))), selected = "All")
  updateSelectInput(session, "virus", choices = c("All", sort(unique(raw_data$AllViruses))), selected = "All")
  updateSelectInput(session, "emergence", choices = c("All", sort(unique(raw_data$Emergence))), selected = "All")
  
  filtered_data <- reactive({
    df <- raw_data
    if (input$year != "All") df <- df |> filter(Year == input$year)
    if (input$country != "All") df <- df |> filter(Country == input$country)
    if (input$virus != "All") df <- df |> filter(AllViruses == input$virus)
    if (input$emergence != "All") df <- df |> filter(Emergence == input$emergence)
    df |> 
      st_as_sf(coords = c("longitude", "latitude"), crs = 4326) |> 
      st_jitter(factor = 0.01)
  })
  
  known_colors <- list(
    "cVDPV1" = "#F067A6",
    "cVDPV2" = "#3ABB9C",
    "cVDPV3" = "#8ED8F8",
    "WPV1"   = "#FF0000",
    "VDPV1"  = "#305cde",
    "VDPV2"  = "#F254F0",
    "VDPV3"  = "orange"
  )
  
  africa_bbox <- c(-20, -35, 55, 38)
  
  render_heatmap <- reactive({
    polio_data <- filtered_data()
    all_types <- unique(polio_data$AllViruses)
    virus_colors <- setNames(
      c(unlist(known_colors), rep("grey", sum(!(all_types %in% names(known_colors))))),
      c(names(known_colors), all_types[!(all_types %in% names(known_colors))])
    )
    
    polio_data$popup_content <- paste(
      "<b>Country:</b>", polio_data$Country, "<br>",
      "<b>DONSET:</b>", format(as.Date(polio_data$DONSET), "%d-%b-%Y"), "<br>",
      "<b>Virus Type:</b>", polio_data$VirusType, "<br>",
      "<b>Emergence:</b>", polio_data$Emergence, "<br>",
      "<b>EPID:</b>", polio_data$EPID, "<br>",
      "<b>Province:</b>", polio_data$Province, "<br>",
      "<b>District:</b>", polio_data$District
    )
    
    heatmap_map <- maplibre(
      style = maptiler_style("openstreetmap"),
      bounds = africa_bbox
    ) |>
      add_heatmap_layer(
        id = "polio_heatmap",
        source = polio_data,
        heatmap_radius = 12,
        heatmap_color = interpolate(
          property = "heatmap-density",
          values = seq(0, 1, length.out = 5),
          stops = c("transparent", "palegreen", "yellow", "orange", "red")
        ),
        heatmap_opacity = interpolate(
          property = "zoom",
          values = c(3, 6),
          stops = c(0.6, 0)
        )
      )
    
    for (virus_type in names(virus_colors)) {
      heatmap_map <- heatmap_map |>
        add_circle_layer(
          id = paste0("circle_", virus_type),
          source = polio_data |> filter(VirusType == virus_type),
          circle_color = virus_colors[[virus_type]],
          circle_radius = 6,
          circle_stroke_color = "black",
          circle_stroke_width = 1,
          min_zoom = 5.0,
          popup = "popup_content"
        )
    }
    
    legend_html <- '
    <div style="background: white; padding: 10px; border-radius: 5px; font-size: 13px; line-height: 1.5; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">
      <strong>Polio Virus Type</strong><br>
      <span style="color:#F067A6;">■</span> cVDPV1<br>
      <span style="color:#3ABB9C;">■</span> cVDPV2<br>
      <span style="color:#8ED8F8;">■</span> cVDPV3<br>
      <span style="color:#FF0000;">■</span> WPV1<br>
      <span style="color:#305cde;">■</span> VDPV1<br>
      <span style="color:#F254F0;">■</span> VDPV2<br>
      <span style="color:orange;">■</span> VDPV3<br>
      <span style="color:grey;">■</span> Other
    </div>'
    
    heatmap_map |> add_control(html = legend_html, position = "bottom-left")
  })
  
  output$heatmap <- renderMaplibre({
    render_heatmap()
  })
  
  output$download_heatmap <- downloadHandler(
    filename = function() paste0("polio_heatmap_", Sys.Date(), ".png"),
    content = function(file) {
      temp_html <- tempfile(fileext = ".html")
      saveWidget(render_heatmap(), file = temp_html, selfcontained = TRUE)
      webshot(temp_html, file = file, vwidth = 1200, vheight = 800)
    }
  )
  
  output$clustermap <- renderMaplibre({
    polio_data <- filtered_data()
    all_types <- unique(polio_data$AllViruses)
    virus_colors <- setNames(
      c(unlist(known_colors), rep("grey", sum(!(all_types %in% names(known_colors))))),
      c(names(known_colors), all_types[!(all_types %in% names(known_colors))])
    )
    
    legend_html <- '
    <div style="background: white; padding: 10px; border-radius: 5px; font-size: 13px; line-height: 1.5; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">
      <strong>Polio Virus Type</strong><br>
      <span style="color:#F067A6;">■</span> cVDPV1<br>
      <span style="color:#3ABB9C;">■</span> cVDPV2<br>
      <span style="color:#8ED8F8;">■</span> cVDPV3<br>
      <span style="color:#FF0000;">■</span> WPV1<br>
      <span style="color:#305cde;">■</span> VDPV1<br>
      <span style="color:#F254F0;">■</span> VDPV2<br>
      <span style="color:orange;">■</span> VDPV3<br>
      <span style="color:grey;">■</span> Other
    </div>'
    
    cluster_map <- maplibre(
      style = maptiler_style("openstreetmap"),
      bounds = africa_bbox
    ) |>
      add_circle_layer(
        id = "polio_clusters",
        source = polio_data,
        circle_color = list(
          property = "AllViruses",
          type = "categorical",
          stops = lapply(names(virus_colors), function(v) list(v, virus_colors[[v]]))
        ),
        circle_stroke_color = "black",
        circle_stroke_width = 1,
        min_zoom = 4,
        popup = NULL,
        cluster_options = cluster_options(
          cluster_radius = 40,
          color_stops = c("#2b83ba", "#abdda4", "#fdae61"),
          count_stops = c(0, 50, 200),
          circle_blur = 0.2,
          circle_stroke_width = 3
        )
      ) |>
      add_control(html = legend_html, position = "bottom-left")
    
    cluster_map
  })
}

shinyApp(ui = ui, server = server)
