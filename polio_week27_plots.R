# =============================================================================
# Week 27, 2025: poliovirus detection plots
# Author: John Kapoi Kipterer
#
# The data is written into the script below, so it runs without reading any
# file. To plot a new week, paste the new rows into `raw_txt` (tab separated,
# copied straight from Excel with the header row).
#
# Outputs (in out_dir):
#   Fig1_country_category.png   detections by country and virus category
#   Fig2_source.png             detections by source
#   Fig3_onset_to_receipt.png   onset/collection to lab receipt, per detection
#   Fig4_nt_difference.png      nucleotide difference from Sabin, per detection
#   Week27_2025_Dashboard.png   all four on one page
#
# Usage: Rscript polio_week27_plots.R [out_dir]
# =============================================================================

# ---- 1. Packages -------------------------------------------------------------
pkgs <- c("dplyr", "stringr", "forcats", "lubridate", "ggplot2", "patchwork")
need <- pkgs[!pkgs %in% rownames(installed.packages())]
if (length(need)) install.packages(need)
suppressPackageStartupMessages(invisible(lapply(pkgs, library, character.only = TRUE)))

# ---- 2. Settings -------------------------------------------------------------
args       <- commandArgs(trailingOnly = TRUE)
out_dir    <- if (length(args)) args[1] else "plots"
report_lab <- "Epi week 27, 2025"
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

cat_order <- c("WPV1", "WPV3", "cVDPV1", "cVDPV2", "cVDPV3",
               "VDPV1", "VDPV2", "VDPV3", "aVDPV1", "aVDPV2", "aVDPV3",
               "iVDPV1", "iVDPV2", "iVDPV3")
src_label <- c(AFP = "AFP", CONTACT = "Contact", HC = "Healthy child",
               COMMUNITY = "Community", ENV = "ENV")

dat <- raw |>
  transmute(
    EPID     = str_squish(EPID_Number),
    Country  = str_to_title(str_squish(Country)),
    Category = str_squish(WPV_VDPV_Category),
    Source   = str_squish(toupper(Source_Case_ENV_Contact_HC)),
    Onset    = to_date(OnsetDate),
    Received = to_date(Date_Received),
    NT_Diff  = suppressWarnings(as.integer(NucleotideDifference_SABIN)),
    Days     = as.integer(Received - Onset)
  ) |>
  mutate(
    Category = fct_relevel(factor(Category),
                           \(lv) c(intersect(cat_order, lv), sort(setdiff(lv, cat_order)))),
    Source   = fct_relabel(factor(Source), \(lv) coalesce(unname(src_label[lv]), lv))
  )

# ---- 5. Look and feel --------------------------------------------------------
# Fixed colour per virus category, so a category keeps its colour in every
# figure and every week. Colour-blind-safe set; categories not listed use grey.
cat_cols <- c(cVDPV2 = "#2a78d6", cVDPV3 = "#eb6834", VDPV2 = "#1baf7a",
              cVDPV1 = "#4a3aa7", VDPV1 = "#e87ba4", WPV1 = "#e34948")
cat_cols <- c(cat_cols, setNames(rep("#8a8985", nlevels(dat$Category)),
                                 setdiff(levels(dat$Category), names(cat_cols))))
single_col <- "#2a78d6"
ink        <- "#0b0b0b"
ink_soft   <- "#52514e"
grid_col   <- "#e6e5e0"

theme_polio <- function() {
  theme_minimal(base_size = 11) +
    theme(
      text               = element_text(colour = ink),
      plot.title         = element_text(face = "bold", size = 12),
      plot.subtitle      = element_text(colour = ink_soft, size = 9.5),
      plot.caption       = element_text(colour = ink_soft, size = 8, hjust = 0),
      plot.title.position = "plot",
      axis.text          = element_text(colour = ink_soft),
      axis.title         = element_text(colour = ink_soft, size = 9.5),
      panel.grid.major.y = element_blank(),
      panel.grid.minor   = element_blank(),
      panel.grid.major.x = element_line(colour = grid_col, linewidth = 0.3),
      legend.position    = "top",
      legend.justification = "left",
      legend.title       = element_text(size = 9.5, colour = ink_soft),
      plot.background    = element_rect(fill = "white", colour = NA)
    )
}
caption_txt <- sprintf("Source: WHO AFRO polio laboratory results, %s.", report_lab)
fill_cat    <- scale_fill_manual(values = cat_cols, name = "Virus category", drop = TRUE)
colour_cat  <- scale_colour_manual(values = cat_cols, name = "Virus category", drop = TRUE)

save_png <- function(p, file, w = 7, h = 4.2) {
  ggsave(file.path(out_dir, file), p, width = w, height = h, dpi = 300, bg = "white")
}

# ---- 6. Figure 1: country x virus category -----------------------------------
by_country <- dat |> count(Country, Category)
country_order <- by_country |> count(Country, wt = n) |> arrange(n, desc(Country)) |> pull(Country)

f1 <- ggplot(by_country, aes(x = n, y = factor(Country, levels = country_order), fill = Category)) +
  geom_col(width = 0.6, colour = "white", linewidth = 0.6) +
  geom_text(data = by_country |> count(Country, wt = n, name = "total"),
            aes(x = total, y = Country, label = total), inherit.aes = FALSE,
            hjust = -0.6, size = 3.4, colour = ink) +
  fill_cat +
  scale_x_continuous(breaks = function(l) seq(0, ceiling(l[2]), 1),
                     expand = expansion(mult = c(0, 0.12))) +
  labs(title = "New poliovirus detections by country and virus category",
       subtitle = sprintf("%s; %d detections in %d countries",
                          report_lab, nrow(dat), n_distinct(dat$Country)),
       x = "Detections", y = NULL, caption = caption_txt) +
  theme_polio()

# ---- 7. Figure 2: detections by source ---------------------------------------
by_source <- dat |> count(Source) |> mutate(Source = fct_reorder(Source, n))

f2 <- ggplot(by_source, aes(x = n, y = Source)) +
  geom_col(width = 0.6, fill = single_col) +
  geom_text(aes(label = n), hjust = -0.6, size = 3.4, colour = ink) +
  scale_x_continuous(breaks = function(l) seq(0, ceiling(l[2]), 1),
                     expand = expansion(mult = c(0, 0.12))) +
  labs(title = "New detections by source",
       subtitle = "AFP case, contact, healthy child or environmental (ENV) sample",
       x = "Detections", y = NULL, caption = caption_txt) +
  theme_polio()

# ---- 8. Figure 3: onset / collection to lab receipt --------------------------
timeline <- dat |>
  filter(!is.na(Onset), !is.na(Received)) |>
  mutate(Label = sprintf("%s (%s)", EPID, Source),
         Label = fct_reorder(Label, Days))

f3 <- ggplot(timeline, aes(y = Label)) +
  geom_segment(aes(x = Onset, xend = Received, yend = Label),
               colour = grid_col, linewidth = 1.6, lineend = "round") +
  geom_point(aes(x = Onset, colour = Category), size = 2.8) +
  geom_point(aes(x = Received), shape = 21, fill = "white", colour = ink_soft,
             size = 2.6, stroke = 0.8) +
  geom_text(aes(x = Received, label = paste0(Days, " d")),
            hjust = -0.4, size = 3, colour = ink_soft) +
  colour_cat +
  scale_x_date(date_labels = "%d %b", date_breaks = "1 month",
               expand = expansion(mult = c(0.03, 0.10))) +
  labs(title = "Time from onset / collection to receipt at the laboratory",
       subtitle = "Filled dot = onset or collection date; open dot = date received; label = days",
       x = NULL, y = NULL, caption = caption_txt) +
  theme_polio() +
  theme(axis.text.y = element_text(size = 8))

# ---- 9. Figure 4: nucleotide difference from Sabin ---------------------------
nt <- dat |>
  filter(!is.na(NT_Diff)) |>
  mutate(EPID = fct_reorder(EPID, NT_Diff))

f4 <- ggplot(nt, aes(x = NT_Diff, y = EPID)) +
  geom_segment(aes(x = 0, xend = NT_Diff, yend = EPID), colour = grid_col, linewidth = 1.2) +
  geom_point(aes(colour = Category), size = 3) +
  geom_text(aes(label = NT_Diff), nudge_x = 2.5, hjust = 0, size = 3, colour = ink_soft) +
  colour_cat +
  scale_x_continuous(expand = expansion(mult = c(0, 0.10))) +
  labs(title = "Nucleotide difference from Sabin, by detection",
       subtitle = "Number of nucleotide changes in VP1 compared with the Sabin vaccine strain",
       x = "Nucleotide difference", y = NULL, caption = caption_txt) +
  theme_polio() +
  theme(axis.text.y = element_text(size = 8))

# ---- 10. Save ----------------------------------------------------------------
save_png(f1, "Fig1_country_category.png")
save_png(f2, "Fig2_source.png", h = 3)
save_png(f3, "Fig3_onset_to_receipt.png", w = 8, h = 4.2)
save_png(f4, "Fig4_nt_difference.png")

no_cap <- theme(plot.caption = element_blank())
dash <- ((f1 + no_cap) | (f2 + no_cap)) / ((f3 + no_cap) | (f4 + no_cap)) +
  plot_annotation(
    title    = sprintf("New poliovirus detections, %s", report_lab),
    caption  = caption_txt,
    theme    = theme(plot.title = element_text(face = "bold", size = 15),
                     plot.caption = element_text(colour = ink_soft, size = 8, hjust = 0))
  )
save_png(dash, "Week27_2025_Dashboard.png", w = 15, h = 9.5)

# Show in the RStudio plot pane when run interactively
if (interactive()) print(dash)

message("Saved plots to ", normalizePath(out_dir))
