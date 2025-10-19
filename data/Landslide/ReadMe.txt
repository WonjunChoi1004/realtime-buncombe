Title:
Preliminary Landslide Inventory for Landslides Triggered by Hurricane Helene (September 2024)

Authors: 
Paula Burgi, Liam Toney, Elaine Collins, Colleen Murphy, Sonia Ellison, Robert Schmitt, Kate Allstadt, Emily Bedinger, Gina Belair, Eric Bilderback, Lynn Ramon Carlson Dunlap, Bart Cattanach, Matt Crawford, Mason Einbund, Faith Fitzpatrick, David Frost, alex grant, Stephen Hageman, Courtney Hartman, Andrew Heckert, Olivia Hoch, Brad Johnson, Eric Jones, Jeremy Jurgevich, Efstratios Karantanellis, David Korte, Sabrina Martinez, Arthur Merschat, Charles Miles, Robert Sas, Lauren Schaefer, Corey Scheip, Rachel Soobitsky, Brennan Trantham, Anne Witt

URL:
https://www.sciencebase.gov/catalog/item/674634a1d34e6d1dac3abddc

Citation:
Burgi, P.M., Toney, L.D., Collins, E.A., Murphy, C.R., Ellison, S.M., Schmitt, R.G., Allstadt, K.E., Bedinger, E.C., Belair, G.M., Bilderback, E.L., C Carlson, L.R., Cattanach, B., Crawford, M.M., Einbund, M.M., Fitzpatrick, F.A., Frost, D. J., Grant, A.R.R, Hageman, S. J., Hartman, C., Heckert, A.B., Hoch, O.J., Johnson, B., Jones, E.S., Jurgevich, J., Karantanellis, E., Korte, D., Martinez, S.N., Merschat, A.J., Miles, C.P., Sas, R., Schaefer, L.N., Scheip, C., Soobitsky, R., Trantham, B., Witt, A., 2025, Preliminary Landslide Inventory for Landslides Triggered by Hurricane Helene (September 2024): U.S. Geological Survey data release, https://doi.org/10.5066/P14CHGKS. 

Summary: 
We present a preliminary point inventory of landslides triggered by Hurricane Helene, which impacted southern Appalachia between September 25 and 27, 2024. This inventory is a result of a rapid response mapping effort led by the U.S. Geological Survey’s Landslide Assessments, Situational Awareness, and Event Response Research (LASER) project. LASER collaborated with state surveys and landslide researchers to identify landslides and their impacts for situational awareness and emergency response. The area of interest (AOI) for this effort was informed by a preliminary landslide hazard map created for the event (Martinez et al., 2024), and encompasses western North Carolina, as well as parts of Tennessee, Virginia, Georgia, and South Carolina.   

Disclaimer:
Any use of trade, firm, or product names is for descriptive purposes only and does not imply endorsement by the U.S. Government.

Data attributes: 
This is a point inventory that contains the following attributes: ‘Source’ and ‘Impact.’ 

Source: 
The ‘Source’ attribute identifies the data source(s) used to map each landslide. The following are the possible data sources, with their associated abbreviations used to identify them in the data attributes: Sentinel-2 (S2), Planet Labs(PL), CAP imagery (CAP), USGS reconnaissance imagery (UA), NOAA imagery (NO), Media report (MR), Field observation (FO), Personal communication (PC), Department of Transportation, North Carolina or Virginia (DOT). Note that the data source(s) listed in this attribute refer only to those used for mapping a given landslide; this does not imply that the landslide is absent or undocumented in other unlisted sources. We do not provide any specific information or metadata (e.g., footprint ID, imagery date, hyperlinks, etc.) related to the listed source(s) used for mapping a landslide. If multiple data sources were used to identify a landslide, they are listed in alphabetical order. For example, if National Oceanic and Atmospheric Administration (NOAA) imagery, Sentinel-2, and U.S. Geological Survey (USGS) reconnaissance imagery were all used to identify and map a landslide, the source attribute is “NO,S2,UA”.  We relied heavily on Sentinel-2 satellite data during the mapping phase and exclusively during the review phase. This is because, while Sentinel-2 has a lower spatial resolution (10 m) compared to other satellite and aerial sources (ranging from 0.15 to 3 m), it is the only utilized dataset that provides complete coverage of the AOI with pre- and post-event multi-spectral imagery. The primary Sentinel-2 images used were acquired on August 26, 2024, and September 22, 2024 (pre-event), as well as October 2, 5, 7, 10, and 12, 2024 (post-event). To facilitate rapid landslide detection, we derived Normalized Difference Vegetation Index (NDVI) change products using various combinations of the pre- and post-event Sentinel-2 data. NDVI change analysis was instrumental in identifying areas with vegetation loss or damage, thereby helping to pinpoint potential landslide activity in this heavily vegetated region. Additionally, red-green-blue (RGB) composite imagery from both pre- and post-event acquisitions was used to validate that NDVI changes were indeed indicative of landslides. Details on these data sources and analysis methods area can be found in Burgi et al. (2024).

Impact: 
The ‘Impact’ attribute indicates the primary impact of a landslide. The following are the options for the Impact attribute: River, Road, Building, Other, Various, NONE, UNCLEAR. A landslide is deemed to have an impact if it appears to intersect with river(s) (including streams and creeks), road(s), building(s), or other human-modified land or infrastructure (e.g., bridges, railroads, powerlines, trails, agricultural fields, lawns, etc.) Impact was determined to the best of a mapper’s ability with the available data and at the time that the imagery was acquired. Many landslides had multiple impacts; however, in most cases, a primary impact could be identified. For example, many landslides appeared to severely impact a road and continue to fail into a nearby river, with no visible impact on the river. In this case, the primary impact would be “road.” If a landslide appeared to have multiple and equally significant impacts, it was classified as “various.” We do not report the number of impacts; for example, a landslide with a “building” impact may have impacted more than one building.

Mapping and review process: 
Emergency response landslide mapping efforts took place between September 28 to October 23, 2024. All landslides were mapped with a single point, irrespective of size or impact. Given the urgency of providing situational awareness for emergency response, landslide points were placed at the location of greatest visible impact, such as buildings, roads, and rivers, rather than at the headscarp. In cases where there was no visible impact, the landslide point was placed at the headscarp. Following the emergency mapping phase, all points underwent a basic review process to refine attributes, remove duplicate/low confidence points, add points for multi-source failures that coalesced into a single failure, and, where possible, adjust point locations from impact zones to the landslide headscarp(s). This data release contains only the “reviewed” version of this inventory. Reviewers utilized only Sentinel-2 NDVI and RGB imagery (pre- and post-event) for reference during the review process, relying most heavily on the September 22 pre-event and October 12 post-event products. Impactful landslides not clearly visible in the Sentinel-2 data (likely mapped using higher resolution data) were not repositioned to a headscarp and may remain at the impact location. 

Uncertainty: 
Due to the rapid and extensive nature of this mapping effort, a formal and systematic assessment of the positional accuracy of the mapped points has not yet been conducted. As a result, there may be some degree of uncertainty in the location and classification of landslides within this inventory. We estimate our accuracy of most landslide headscarp points to be within tens of meters of their correct location. However, in some cases, dense vegetation and imaging geometry may obscure the true headscarp location, further decreasing the accuracy of some mapped landslide points. Furthermore, field or high-resolution validation was not possible for every landslide. Therefore, some mapped points may not correspond to actual landslide events. In particular, distinguishing landslides from severe tree blowdowns or areas of recently human-modified land cover (e.g., clearcutting or construction activities) sometimes proved challenging. It is possible that a small number of points mistakenly represent these features instead of genuine landslides. Finally, it is important to note that this inventory is preliminary and does not capture the full extent of landslides triggered by Hurricane Helene. Factors such as the rapid response nature of the mapping effort, limitations in imagery resolution, and dense forest canopy that obstructed the overhead (i.e., aerial and satellite) view of smaller or non-catastrophic landslides may contribute to underrepresentation of the total landslide count. 


Description of data files: 
HurricaneHelene_LS_Inventory.zip: Zipped folder containing a shapefile and related files. Point landslide inventory with "Source" and "Impact" attributes. 

HurricaneHelene_LS_Inventory.geojson: GeoJSON file. Point landslide inventory with "Source" and "Impact" attributes. 

HurricaneHelene_LS_Inventory.csv: CSV file. Point landslide inventory with four columns, as follows: Column 1: "Longitude," Column 2: "Latitude," Column 3: "Source," and Column 4: "Impact."

Note: The information (geometry and attributes) within the shapefile, GeoJSON, and comma-separated value (CSV) files is identical.


References:
Burgi, P.M., Collins, E.A., Allstadt, K.E., Einbund, M.M., 2024, Normalized Difference Vegetation Index (NDVI) Change Map between 9/22/2024 and 10/12/2024, Southern Appalachian Mountains: 2024 USGS provisional data release. https://doi.org/10.5066/P14KDUKK.

Martinez, S.N., Stanley, T., Allstadt, K.E., Baxstrom, K.W., Mirus, B.B., Einbund, M.M., Bedinger, E.C., 2024, Preliminary Landslide Hazard Models for the 2024 Hurricane Helene Landslide Emergency Response: 2024 USGS Provisional Data Release. https://doi.org/10.5066/P134ERB9.


Purpose: 
Hurricanes can impact regions with heavy precipitation and strong winds and may result in wide-spread and numerous landslides. Rapid response landslide inventories during these events provide timely science information to partner agencies, emergency responders, and the public.


