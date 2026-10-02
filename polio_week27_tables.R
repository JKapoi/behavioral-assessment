# =============================================================================
# Week 27, 2025: poliovirus detection tables (3 versions)
# Author: John Kapoi Kipterer
#
# Input: every Excel file in data_dir, with these columns:
#   Date_Received, EPID_Number, WPV_VDPV_Category, Source_Case_ENV_Contact_HC,
#   Country, Province, District, SiteName_Geocode, OnsetDate,
#   NucleotideDifference_SABIN, ClusterLineage, Closest_Match_VDPV1_2,
#   Week_Num, Country_Province_District, Pcode-Admin2
#
# Each row is one detection (AFP case, contact, healthy child or ENV sample).
#
# Outputs (in data_dir/outputs):
#   Week27_2025_Tables.xlsx   three sheets, one per table
#   Week27_2025_Tables.docx   landscape Word report with the three tables
#
#   Table 1  New detections by country and virus category
#   Table 2  New detections by country, virus category and source
#   Table 3  Line list by country, province and district
#
# Libraries added over the first version:
#   lubridate  date parsing (Excel serials, d/m/Y, Y-m-d, date-times)
#   purrr      reading many files and building the sheets / Word sections
#   forcats    display order and labels for virus categories and sources
#
# Usage: Rscript polio_week27_tables.R [data_dir]
# =============================================================================

# ---- 1. Packages -------------------------------------------------------------
pkgs <- c("readxl", "dplyr", "tidyr", "stringr", "openxlsx", "flextable",
          "officer", "lubridate", "purrr", "forcats")
need <- pkgs[!pkgs %in% rownames(installed.packages())]
if (length(need)) install.packages(need)
suppressPackageStartupMessages(invisible(lapply(pkgs, library, character.only = TRUE)))

# ---- 2. Settings -------------------------------------------------------------
args        <- commandArgs(trailingOnly = TRUE)
data_dir    <- if (length(args)) args[1] else "D:/AAAPEPVirus/AScript/Week_27_2025"
out_dir     <- file.path(data_dir, "outputs")
report_week <- "25-27"          # value(s) in Week_Num to report; NULL = all rows
report_lab  <- "Epi week 27, 2025"
sheet_no    <- 1
source_note <- sprintf("Source: WHO AFRO polio laboratory results, Week_Num %s.",
                       if (is.null(report_week)) "all" else paste(report_week, collapse = ", "))

dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

# ---- 3. Read all Excel files -------------------------------------------------
files <- list.files(data_dir, pattern = "\\.xlsx?$", full.names = TRUE)
files <- files[!str_starts(basename(files), fixed("~$"))]   # skip Excel lock files
if (!length(files)) stop("No Excel files found in ", data_dir)
message("Reading: ", paste(basename(files), collapse = ", "))

raw <- files |>
  set_names(basename) |>
  map(\(f) read_excel(f, sheet = sheet_no, col_types = "text",
                      .name_repair = str_squish)) |>
  list_rbind(names_to = "Source_File")

needed <- c("Date_Received", "EPID_Number", "WPV_VDPV_Category",
            "Source_Case_ENV_Contact_HC", "Country", "Province", "District",
            "SiteName_Geocode", "OnsetDate", "NucleotideDifference_SABIN",
            "ClusterLineage", "Closest_Match_VDPV1_2", "Week_Num")
miss <- setdiff(needed, names(raw))
if (length(miss)) stop("Missing column(s): ", paste(miss, collapse = ", "))

# ---- 4. Clean ----------------------------------------------------------------
# Dates may arrive as Excel serials (45839), text (29/05/2025, 2025-05-29)
# or date-times (2025-05-29 00:00:00)
to_date <- function(x) {
  x      <- str_squish(x)
  serial <- !is.na(x) & str_detect(x, "^\\d+(\\.\\d+)?$")
  out    <- as_date(rep(NA_real_, length(x)))
  out[serial]  <- as_date(floor(as.numeric(x[serial])), origin = "1899-12-30")
  out[!serial] <- as_date(parse_date_time(
    x[!serial], orders = c("dmy", "ymd", "dmy HMS", "ymd HMS", "dmy HM"),
    quiet = TRUE))
  out
}

blank_na <- function(x) {
  x <- str_squish(x)
  if_else(is.na(x) | x == "" | toupper(x) == "N/A", NA_character_, x)
}

dat <- raw |>
  transmute(
    Week_Num      = str_squish(Week_Num),
    Country       = str_squish(toupper(Country)),
    Province      = str_squish(toupper(Province)),
    District      = str_squish(toupper(District)),
    Category      = blank_na(WPV_VDPV_Category),
    Source        = str_squish(toupper(Source_Case_ENV_Contact_HC)),
    EPID          = blank_na(EPID_Number),
    Site          = blank_na(SiteName_Geocode),
    Onset         = to_date(OnsetDate),
    Received      = to_date(Date_Received),
    NT_Diff       = suppressWarnings(as.integer(NucleotideDifference_SABIN)),
    Emergence     = blank_na(ClusterLineage),
    Closest_Match = blank_na(Closest_Match_VDPV1_2),
    Source_File
  ) |>
  filter(!is.na(Country), Country != "", !is.na(Category))

if (!is.null(report_week)) dat <- filter(dat, Week_Num %in% report_week)
if (!nrow(dat)) stop("No rows for Week_Num = ", paste(report_week, collapse = ", "))

# Guard against the same EPID appearing twice (e.g. in two input files).
# Rows without an EPID are kept: distinct() would otherwise collapse them into one.
dups <- dat |> filter(!is.na(EPID), duplicated(EPID))
if (nrow(dups)) {
  message("Dropping ", nrow(dups), " duplicate EPID row(s): ",
          paste(unique(dups$EPID), collapse = ", "))
}
dat <- dat |> filter(is.na(EPID) | !duplicated(EPID))

bad_dates <- dat |> filter(!is.na(Onset), !is.na(Received), Received < Onset)
if (nrow(bad_dates)) {
  warning(nrow(bad_dates), " row(s) received before onset: ",
          paste(coalesce(bad_dates$EPID, bad_dates$Site), collapse = ", "),
          call. = FALSE)
}
message(nrow(dat), " detection(s) for ", report_lab)

# Fixed display order for virus categories and sources; unknown values go last
cat_order <- c("WPV1", "WPV3", "cVDPV1", "cVDPV2", "cVDPV3",
               "VDPV1", "VDPV2", "VDPV3", "aVDPV1", "aVDPV2", "aVDPV3",
               "iVDPV1", "iVDPV2", "iVDPV3")
src_label <- c(AFP = "AFP", CONTACT = "Contact", HC = "Healthy child",
               COMMUNITY = "Community", ENV = "ENV")

order_known_first <- function(f, known) {
  lv <- levels(f)
  fct_relevel(f, c(intersect(known, lv), sort(setdiff(lv, known))))
}

dat <- dat |>
  mutate(
    Category = Category |> factor() |> order_known_first(cat_order),
    Source   = Source |> factor() |> order_known_first(names(src_label)) |>
      fct_relabel(\(lv) coalesce(unname(src_label[lv]), lv))
  )

add_total_row <- function(df, label_col = 1) {
  num <- map_lgl(df, is.numeric)
  tot <- as.list(rep("", ncol(df))) |> set_names(names(df))
  tot[[label_col]] <- "Total"
  tot[num] <- map(df[num], \(v) sum(v, na.rm = TRUE))
  bind_rows(mutate(df, across(!where(is.numeric), as.character)),
            as_tibble(tot))
}

# ---- 5. Table 1: country x virus category ------------------------------------
t1 <- dat |>
  count(Country, Category) |>
  pivot_wider(names_from = Category, values_from = n, values_fill = 0,
              names_sort = TRUE) |>
  mutate(Total = rowSums(across(-Country))) |>
  arrange(desc(Total), Country) |>
  add_total_row()

# ---- 6. Table 2: country x virus category x source ---------------------------
t2 <- dat |>
  count(Country, Category, Source) |>
  pivot_wider(names_from = Source, values_from = n, values_fill = 0,
              names_sort = TRUE) |>
  mutate(Total = rowSums(across(-c(Country, Category)))) |>
  arrange(Country, Category) |>
  rename(`Virus category` = Category) |>
  add_total_row()

# ---- 7. Table 3: line list by province and district --------------------------
fmt_d <- function(d) if_else(is.na(d), "", format(d, "%d %b %Y"))

t3 <- dat |>
  arrange(Country, Province, District, Category, Onset) |>
  transmute(
    Country, Province, District,
    `Virus category`      = as.character(Category),
    Source                = as.character(Source),
    `EPID number`         = coalesce(EPID, ""),
    `ENV site`            = coalesce(Site, ""),
    `Onset / collection`  = fmt_d(Onset),
    `Date received`       = fmt_d(Received),
    `Days to receipt`     = as.integer(Received - Onset),
    `NT diff. (Sabin)`    = NT_Diff,
    `Emergence group`     = coalesce(Emergence, ""),
    `Closest match`       = coalesce(Closest_Match, "")
  )

tables <- list(
  T1_Country_Category = list(
    df = t1, title = "Table 1. New poliovirus detections by country and virus category"),
  T2_Category_Source = list(
    df = t2, title = "Table 2. New poliovirus detections by country, virus category and source"),
  T3_Line_List = list(
    df = t3, title = "Table 3. Line list of new poliovirus detections by province and district")
) |>
  map(\(t) modifyList(t, list(title = paste0(t$title, ", ", report_lab))))

has_total <- function(df) identical(df[[1]][nrow(df)], "Total")

# ---- 8. Excel output ---------------------------------------------------------
wb <- createWorkbook()
st_head  <- createStyle(textDecoration = "bold", fgFill = "#1F4E79",
                        fontColour = "#FFFFFF", halign = "center",
                        valign = "center", border = "TopBottomLeftRight",
                        wrapText = TRUE)
st_title <- createStyle(textDecoration = "bold", fontSize = 12)
st_total <- createStyle(textDecoration = "bold", fgFill = "#D9E1F2")
st_note  <- createStyle(fontSize = 9, textDecoration = "italic")

iwalk(tables, \(t, nm) {
  df <- t$df
  addWorksheet(wb, nm, gridLines = FALSE)
  writeData(wb, nm, t$title, startRow = 1)
  addStyle(wb, nm, st_title, rows = 1, cols = 1)
  writeData(wb, nm, df, startRow = 3, headerStyle = st_head, borders = "all")
  setColWidths(wb, nm, cols = seq_len(ncol(df)), widths = "auto")
  freezePane(wb, nm, firstActiveRow = 4)
  if (has_total(df)) {
    addStyle(wb, nm, st_total, rows = 3 + nrow(df), cols = seq_len(ncol(df)),
             gridExpand = TRUE, stack = TRUE)
  }
  writeData(wb, nm, source_note, startRow = 5 + nrow(df))
  addStyle(wb, nm, st_note, rows = 5 + nrow(df), cols = 1)
})
xlsx_out <- file.path(out_dir, "Week27_2025_Tables.xlsx")
saveWorkbook(wb, xlsx_out, overwrite = TRUE)

# ---- 9. Word output ----------------------------------------------------------
make_ft <- function(df) {
  ft <- flextable(df) |>
    theme_box() |>
    bold(part = "header") |>
    bg(part = "header", bg = "#1F4E79") |>
    color(part = "header", color = "white") |>
    fontsize(size = 8, part = "all") |>
    align(align = "center", part = "header") |>
    align(j = which(map_lgl(df, is.numeric)), align = "center", part = "body") |>
    autofit()
  if (has_total(df)) {
    ft <- ft |> bold(i = nrow(df)) |> bg(i = nrow(df), bg = "#D9E1F2")
  }
  ft
}

doc <- read_docx() |>
  body_add_par(sprintf("New poliovirus detections, %s", report_lab), style = "heading 1") |>
  body_add_par(sprintf("%d new detection(s) reported across %d country(ies).",
                       nrow(dat), n_distinct(dat$Country)), style = "Normal")

doc <- reduce(seq_along(tables), \(d, i) {
  d <- d |>
    body_add_par(tables[[i]]$title, style = "heading 2") |>
    body_add_flextable(make_ft(tables[[i]]$df)) |>
    body_add_par(source_note, style = "Normal")
  if (i < length(tables)) body_add_break(d) else d
}, .init = doc)

doc <- body_set_default_section(
  doc, prop_section(page_size = page_size(orient = "landscape")))

docx_out <- file.path(out_dir, "Week27_2025_Tables.docx")
print(doc, target = docx_out)

message("Saved:\n  ", xlsx_out, "\n  ", docx_out)
