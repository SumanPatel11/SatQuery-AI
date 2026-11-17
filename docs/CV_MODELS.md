# Computer-Vision Models and Datasets

`cv/registry.py` connects the four model wrappers below. Checkpoints are local artifacts ignored by Git. Capability registration depends on required files being present.

| Capability | Implementation and artifact | Input contract | Returned values and limits |
|---|---|---|---|
| SpaceNet2 building detection | `cv/models/building.py`; `runs/detect/runs/detect/spacenet2_building_yolo26n/weights/best.pt`; YOLO26n family | RGB-readable image; CPU inference | Count, confidence, box coordinates, center coordinates, optional annotated image. Count is not accuracy. |
| LoveDA land-cover segmentation | `cv/models/land_cover.py`; `models/cv/loveda_land_cover/best.pt` | RGB-readable image; seven output classes | Background, building, road, water, barren, forest, agriculture; class pixel counts and optional mask. Pixel counts/percentages are not geospatial area. |
| LEVIR-CD building change | `cv/models/change_v2.py`; `models/cv/levir_cd_change_v2/best.pt` | Before/after images with matching dimensions; resized to checkpoint model size (default 256 ? 256) | Changed pixel count/fraction at model resolution; optional mask/probability/overlay. Not physical area or accuracy. |
| Sen1Floods11 flood detection | `cv/models/flood.py`; `models/cv/radiance_sen1floods11_v2/model.py` and `best.pt` | Readable two-band SAR GeoTIFF at least 224 ? 224; 224-pixel sliding windows, stride 112 | Flood, valid, invalid pixel counts; pixel fraction; optional probability map, mask, overlay. Not physical area. |

The inspected executors use CPU inference. The registry reports a capability unavailable when its implementation or required artifact is missing or empty.

## Dataset references and credit

### SpaceNet2

SpaceNet2 provides satellite imagery and building-footprint annotations. Cite Van Etten, Lindenbaum, and Bacastow, ?SpaceNet: A Remote Sensing Dataset and Challenge Series? (2018), [arXiv:1807.01232](https://arxiv.org/abs/1807.01232). Details and stated license are on the [SpaceNet2 dataset page](https://spacenet.ai/spacenet-buildings-dataset-v2/).

### LoveDA

Cite Wang, Zheng, Ma, Lu, and Zhong, ?LoveDA: A Remote Sensing Land-Cover Dataset for Domain Adaptive Semantic Segmentation,? NeurIPS Datasets and Benchmarks (2021), [arXiv:2110.08733](https://arxiv.org/abs/2110.08733). Dataset record: [Zenodo DOI 10.5281/zenodo.5706578](https://doi.org/10.5281/zenodo.5706578).

### LEVIR-CD

Cite Chen and Shi, ?A Spatial-Temporal Attention-Based Method and a New Dataset for Remote Sensing Image Change Detection,? *Remote Sensing* 12(10), 1662 (2020), [DOI 10.3390/rs12101662](https://doi.org/10.3390/rs12101662). See the [dataset owners? page](https://justchenhao.github.io/LEVIR/) for access and usage terms. The authors state restrictions on commercial use; follow current terms for redistribution or external evaluation.

### Sen1Floods11

Cite Bonafilia, Tellman, Anderson, and Issenberg, ?Sen1Floods11: A Georeferenced Dataset to Train and Test Deep Learning Flood Algorithms for Sentinel-1,? CVPR Workshops (2020), [CVF Open Access paper](https://openaccess.thecvf.com/content_CVPRW_2020/html/w11/Bonafilia_Sen1Floods11_A_Georeferenced_Dataset_to_Train_and_Test_Deep_Learning_CVPRW_2020_paper.html). The [dataset repository](https://github.com/cloudtostreet/Sen1Floods11) provides current data notes and citation guidance.

Dataset names identify data used in the project; they do not imply that current checkpoints reproduce the original papers? benchmark results. Check dataset-owner terms before use or redistribution.
