# =============================================================================
# Week 27, 2025: poliovirus detection tables drawn with ggplot2
# Author: John Kapoi Kipterer
#
# The data is written into the script below, so it runs without reading any
# file. To plot a new week, paste the new rows into `raw_txt` (tab separated,
# copied straight from Excel with the header row).
#
# Outputs (in out_dir), one PNG per table:
#   Table1_country_category.png   detections by country and virus category
#   Table2_category_source.png    detections by country, virus category and source
#   Table3_line_list.png          line list by country, province and district
#
# In RStudio: click Source, then print(p1), print(p2) or print(p3).
# Usage: Rscript polio_week27_table_plots.R [out_dir]
# =============================================================================

# ---- 1. Packages -------------------------------------------------------------
pkgs <- c("dplyr", "tidyr", "stringr", "forcats", "lubridate", "ggplot2")
need <- pkgs[!pkgs %in% rownames(installed.packages())]
if (length(need)) install.packages(need)
suppressPackageStartupMessages(invisible(lapply(pkgs, library, character.only = TRUE)))

# ---- 2. Settings -------------------------------------------------------------
args        <- commandArgs(trailingOnly = TRUE)
out_dir     <- if (length(args)) args[1] else "table_plots"
report_lab  <- "Epi week 27, 2025"
caption_txt <- sprintf("Source: WHO AFRO polio laboratory results, %s.", report_lab)
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

# ---- 3. Data -----------------------------------------------------------------
raw_txt <- "
Date_Received\tEPID_Number\tWPV_VDPV_Category\tSource_Case_ENV_Contact_HC\tCountry\tProvince\tDistrict\tSiteName_Geocode\tOnsetDate\tNucleotideDifference_SABIN\tClusterLineage\tClosest_Match_VDPV1_2\tWeek_Num
45839\tENV-CHA-NDJ-NDS-CCM-25-011\tcVDPV2\tENV\tCHAD\tN'DJAMENA\tN'DJAMENA SUD\tCANAL CHARI MONGO\t29/05/2025\t52\tNIE-ZAS-1\tTBU\t25-27
45839\tCAE-ADA-NGR-25-030\tcVDPV3\tAFP\tCAMEROON\tADAMAOUA\tNGAOUNDERE RURAL\tN/A\t30/05/2025\t52\tGUI-KAN-1\tGUI-FAR-KIS-25-167\t25-27
45839\tCHA-NDJ-ND8-25-0419\tcVDPV2\tAFP\tCHAD\tN'DJAMENA\tN'DJAMENA CENTRE\tN/A\t15/05/2025\t54\tNIE-ZAS-1\tCHA-25-CAE-25-01036\t25-27
45840\tNIE-JIS-GRM-25-012C1\tcVDPV2\tCONTACT\tNIGERIA\tJIGAWA\tGWARAM\tN/A\t07/05/2025\t56\tNIE-ZAS-1\tNIE-JIS-KYW-24-030\t25-27
45840\tENV-NIE-SOS-SKK-KKR-25-011\tVDPV2\tENV\tNIGERIA\tSOKOTO\tSOKOTO NORTH\tKOFAR KWARE\t02/06/2025\t6\tTBU\tnOPV2\t25-27
45842\tRSS-WBG-WAU-25-004\tVDPV2\tAFP\tSOUTH SUDAN\tWESTERN BAHR EL GHAZAL\tWAU\tN/A\t10/05/2025\t8\tTBU\tnOPV2\t25-27
45842\tETH-ORO-EHA-25-0322\tcVDPV2\tAFP\tETHIOPIA\tOROMIYA\tEAST HARARGE\tN/A\t20/02/2025\t78\tSOM-BAN-1\tETH-ORO-EHA-24-1537\t25-27
"
raw <- read.delim(text = str_trim(raw_txt), sep = "\t", quote = "",
                  colClasses = "character", check.names = FALSE)

# ---- 4. Clean ----------------------------------------------------------------
# Dates may be Excel serials (45839) or text (29/05/2025)
to_date <- function(x) {
  x      <- str_squish(x)
  serial <- !is.na(x) & str_detect(x, "^\\d+(\\.\\d+)?$")
  out    <- as_date(rep(NA_real_, length(x)))
  out[serial]  <- as_date(floor(as.numeric(x[serial])), origin = "1899-12-30")
  out[!serial] <- as_date(parse_date_time(x[!serial], c("dmy", "ymd"), quiet = TRUE))
  out
}
blank_na <- function(x) {
  x <- str_squish(x)
  if_else(is.na(x) | x == "" | toupper(x) == "N/A", NA_character_, x)
}

cat_order <- c("WPV1", "WPV3", "cVDPV1", "cVDPV2", "cVDPV3",
               "VDPV1", "VDPV2", "VDPV3", "aVDPV1", "aVDPV2", "aVDPV3",
               "iVDPV1", "iVDPV2", "iVDPV3")
src_label <- c(AFP = "AFP", CONTACT = "Contact", HC = "Healthy child",
               COMMUNITY = "Community", ENV = "ENV")

dat <- raw |>
  transmute(
    Country       = str_to_title(str_squish(Country)),
    Province      = str_squish(toupper(Province)),
    District      = str_squish(toupper(District)),
    Category      = str_squish(WPV_VDPV_Category),
    Source        = str_squish(toupper(Source_Case_ENV_Contact_HC)),
    EPID          = str_squish(EPID_Number),
    Site          = blank_na(SiteName_Geocode),
    Onset         = to_date(OnsetDate),
    Received      = to_date(Date_Received),
    NT_Diff       = suppressWarnings(as.integer(NucleotideDifference_SABIN)),
    Emergence     = blank_na(ClusterLineage),
    Closest_Match = blank_na(Closest_Match_VDPV1_2)
  ) |>
  mutate(
    Category = fct_relevel(factor(Category),
                           \(lv) c(intersect(cat_order, lv), sort(setdiff(lv, cat_order)))),
    Source   = fct_relabel(factor(Source), \(lv) coalesce(unname(src_label[lv]), lv))
  )

# ---- 5. Build the tables -----------------------------------------------------
add_total_row <- function(df) {
  num <- vapply(df, is.numeric, logical(1))
  tot <- as.list(rep("", ncol(df))) |> setNames(names(df))
  tot[[1]] <- "Total"
  tot[num] <- lapply(df[num], sum, na.rm = TRUE)
  bind_rows(mutate(df, across(!where(is.numeric), as.character)), as_tibble(tot))
}

t1 <- dat |>
  count(Country, Category) |>
  pivot_wider(names_from = Category, values_from = n, values_fill = 0, names_sort = TRUE) |>
  mutate(Total = rowSums(across(-Country))) |>
  arrange(desc(Total), Country) |>
  add_total_row()

t2 <- dat |>
  count(Country, Category, Source) |>
  pivot_wider(names_from = Source, values_from = n, values_fill = 0, names_sort = TRUE) |>
  mutate(Total = rowSums(across(-c(Country, Category)))) |>
  arrange(Country, Category) |>
  rename(`Virus category` = Category) |>
  add_total_row()

t3 <- dat |>
  arrange(Country, Province, District, Category, Onset) |>
  transmute(
    Country, Province, District,
    `Virus\ncategory`     = as.character(Category),
    Source                = as.character(Source),
    `EPID number`         = EPID,
    `ENV site`            = Site,
    `Onset /\ncollection` = format(Onset, "%d %b %Y"),
    `Date\nreceived`      = format(Received, "%d %b %Y"),
    `Days to\nreceipt`    = as.integer(Received - Onset),
    `NT diff.\n(Sabin)`   = NT_Diff,
    `Emergence\ngroup`    = Emergence,
    `Closest match`       = Closest_Match
  )

# ---- 6. Draw a table with ggplot2 --------------------------------------------
# Each cell is a geom_tile with a geom_text label. Column widths follow the
# longest text in each column; numbers are centred, text is left-aligned.
header_fill <- "#1F4E79"
band_fill   <- "#F4F6FA"
total_fill  <- "#D9E1F2"
line_col    <- "#C9CED8"
ink         <- "#0B0B0B"
ink_soft    <- "#52514E"

gg_table <- function(df, title, text_size = 3.2) {
  num   <- vapply(df, is.numeric, logical(1))
  n     <- nrow(df)
  total <- identical(df[[1]][n], "Total")

  # Column widths in "characters", from the longest header line or cell
  head_len <- vapply(str_split(names(df), "\n"), \(s) max(nchar(s)), numeric(1))
  cell_len <- vapply(df, \(v) max(nchar(coalesce(as.character(v), ""))), numeric(1))
  widths   <- pmax(head_len, cell_len) + 3
  x_right  <- cumsum(widths)
  x_left   <- x_right - widths

  head_h <- if (any(str_detect(names(df), "\n"))) 1.7 else 1.1
  cols   <- tibble(col = seq_along(df), name = names(df), num = num,
                   xmin = x_left, xmax = x_right)

  header <- cols |>
    mutate(ymin = -head_h, ymax = 0, label = name, fill = "header",
           face = "bold", colour = "white", hjust = 0.5, x = (xmin + xmax) / 2)

  body <- df |>
    mutate(across(everything(), \(v) coalesce(as.character(v), "")),
           row = row_number()) |>
    pivot_longer(-row, names_to = "name", values_to = "label") |>
    left_join(cols, by = "name") |>
    mutate(
      ymin   = row - 1, ymax = row,
      fill   = case_when(total & row == n ~ "total",
                         row %% 2 == 0    ~ "band",
                         TRUE             ~ "plain"),
      face   = if_else(total & row == n, "bold", "plain"),
      colour = ink,
      hjust  = if_else(num, 0.5, 0),
      x      = if_else(num, (xmin + xmax) / 2, xmin + 1)
    )

  cells <- bind_rows(header, body) |> mutate(y = (ymin + ymax) / 2)

  ggplot(cells) +
    geom_rect(aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax, fill = fill),
              colour = line_col, linewidth = 0.3) +
    geom_text(aes(x = x, y = y, label = label, hjust = hjust,
                  fontface = face, colour = colour),
              size = text_size, lineheight = 0.9) +
    scale_fill_manual(values = c(header = header_fill, band = band_fill,
                                 total = total_fill, plain = "white"), guide = "none") +
    scale_colour_identity() +
    scale_y_reverse(expand = expansion(add = 0.15)) +
    scale_x_continuous(expand = expansion(add = 0.5)) +
    labs(title = title, caption = caption_txt) +
    theme_void(base_size = 11) +
    theme(
      plot.title          = element_text(face = "bold", size = 12, colour = ink,
                                         margin = margin(b = 8)),
      plot.caption        = element_text(colour = ink_soft, size = 8, hjust = 0,
                                         margin = margin(t = 8)),
      plot.title.position = "plot",
      plot.caption.position = "plot",
      plot.margin         = margin(12, 12, 12, 12),
      plot.background     = element_rect(fill = "white", colour = NA)
    )
}

# Picture size that keeps cells readable: about 0.085 in per character of
# table width and 0.3 in per row, never narrower than the title needs.
save_table <- function(p, df, file, title) {
  chars <- sum(vapply(seq_along(df), \(j) {
    max(nchar(c(str_split(names(df)[j], "\n")[[1]], coalesce(as.character(df[[j]]), "")))) + 3
  }, numeric(1)))
  w <- max(chars * 0.085, nchar(title) * 0.095) + 0.4
  h <- 1.3 + 0.3 * (nrow(df) + 1.5)
  ggsave(file.path(out_dir, file), p, width = w, height = h, dpi = 300, bg = "white")
}

titles <- c(
  sprintf("Table 1. New poliovirus detections by country and virus category, %s", report_lab),
  sprintf("Table 2. New poliovirus detections by country, virus category and source, %s", report_lab),
  sprintf("Table 3. Line list of new poliovirus detections by province and district, %s", report_lab)
)

p1 <- gg_table(t1, titles[1])
p2 <- gg_table(t2, titles[2])
p3 <- gg_table(t3, titles[3], text_size = 2.9)

# ---- 7. Save and show --------------------------------------------------------
save_table(p1, t1, "Table1_country_category.png", titles[1])
save_table(p2, t2, "Table2_category_source.png",  titles[2])
save_table(p3, t3, "Table3_line_list.png",        titles[3])

if (interactive()) print(p1)   # print(p2) / print(p3) for the others

message("Saved table plots to ", normalizePath(out_dir))
