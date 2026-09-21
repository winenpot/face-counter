# Proposal: AI-Based Product Face Counting Web Service
## 1. Overview
This proposal describes the development of an internal web service that uses computer vision to automatically identify and count the visible product faces displayed on store shelves.
The service will receive a photograph of a store shelf or product display through an API, analyze the image using a trained computer vision model, and return the number of visible faces belonging to the company's products.
The primary objective is to reduce the need for manual shelf inspection and provide a consistent, machine-assisted method for measuring product presence and shelf visibility across stores, supermarkets, and other retail environments.
## 2. Business Objective
Currently, determining the number of visible product faces on a shelf may require employees or field representatives to manually inspect photographs.
The proposed system will automate this process:
**Store/Shelf Photo → API → Computer Vision Model → Product Detection → Face Count → Structured Result**
The resulting API can subsequently be integrated into existing internal applications, reporting systems, dashboards, or mobile applications.
Potential uses include:
* Measuring product shelf presence.
* Counting visible product faces.
* Monitoring product placement across stores.
* Supporting field-sales and merchandising activities.
* Reducing manual image inspection.
* Producing standardized shelf-visibility measurements.
* Providing data for BI and sales analysis.
## 3. Proposed System
The proposed solution will consist of a web API and a computer vision inference service hosted on the company's server.
A client submits a shelf photograph to the API:
```text
POST /api/v1/shelf-analysis
```
The service processes the image and returns a structured response containing the detected products and their face counts.
Example:
```json
{
"status": "success",
"total_product_faces": 14,
"products": [
{
"product_id": "PRODUCT-001",
"product_name": "Product A",
"face_count": 8
},
{
"product_id": "PRODUCT-002",
"product_name": "Product B",
"face_count": 6
}
]
}
```
The API can also return additional information such as:
* Detection confidence.
* Bounding boxes.
* Image processing time.
* Model version.
* Warnings or quality issues.
* An annotated version of the image for verification.
## 4. System Architecture
A preliminary architecture is:
```text
Client / Internal Application
|
| HTTP
v
┌─────────────┐
│ Caddy │
│ Reverse │
│ Proxy │
└──────┬──────┘
|
v
┌─────────────┐
│ FastAPI │
│ API │
└──────┬──────┘
|
v
┌─────────────┐
│ CV Inference│
│ Service │
└──────┬──────┘
|
v
┌─────────────┐
│ Computer │
│ Vision Model│
└──────┬──────┘
|
v
Detection / Face Count
```
For the initial implementation, the API and inference service can run on the same server if the expected request volume is relatively low.
The architecture should nevertheless keep the API and model inference logically separated so that the inference component can later be moved to a dedicated machine or GPU server without requiring major changes to the client-facing API.
## 5. Computer Vision Component
The core of the system will be an object-detection model trained to recognize the company's products in shelf photographs.
An appropriate starting point is a modern object-detection architecture such as YOLO.
The initial model can be based on a pretrained model and subsequently fine-tuned using company-specific shelf images.
The model should ultimately be capable of detecting individual visible product faces rather than simply determining whether a product exists somewhere in the photograph.
For example:
```text
Shelf Image
┌───────────────────────────────────────┐
│ [Product A] [Product A] [Product A] │
│ [Product A] [Product B] [Product B] │
│ [Product C] [Product C] │
└───────────────────────────────────────┘
Model Output:
Product A → 4 faces
Product B → 2 faces
Product C → 2 faces
Total → 8 faces
```
The exact model architecture will be determined during the experimentation phase based on accuracy, inference speed, available hardware, and the diversity of shelf photographs.
## 6. Dataset and Model Training
The most important component for achieving reliable results will be the quality and diversity of the training dataset.
A dataset should be collected containing representative photographs from actual stores and shelves.
The dataset should cover variations such as:
* Different stores.
* Different shelf configurations.
* Different lighting conditions.
* Different camera devices.
* Different image resolutions.
* Different viewing angles.
* Products partially obscured by other products.
* Products at different distances from the camera.
* Different product orientations.
* Empty or partially empty shelves.
* Crowded shelves.
* Similar-looking products.
The images will then be annotated with bounding boxes identifying the visible product faces.
The dataset should be divided into:
```text
Training Set
Validation Set
Test Set
```
The test set should contain images that were not used during training or model development. Ideally, some stores should be completely excluded from training and used only for final evaluation. This provides a better measurement of how well the system generalizes to previously unseen stores.
## 7. API Design
The initial API could expose endpoints such as:
### Analyze Shelf Image
```http
POST /api/v1/shelf-analysis
```
Input:
```text
multipart/form-data
image=
```
Output:
```json
{
"request_id": "abc123",
"status": "success",
"total_product_faces": 14,
"products": [
{
"product_id": "PRODUCT-001",
"face_count": 8,
"confidence": 0.94
}
],
"model_version": "v1.0"
}
```
### Health Check
```http
GET /health
```
Used by infrastructure and monitoring systems to determine whether the service is operational.
### Model Information
```http
GET /api/v1/model
```
Can return the currently deployed model version and other relevant metadata.
## 8. Image Processing Pipeline
The processing pipeline would approximately be:
```text
1. Receive image
↓
2. Validate image
↓
3. Resize / preprocess
↓
4. Run object detection
↓
5. Filter low-confidence detections
↓
6. Identify product classes
↓
7. Count visible product faces
↓
8. Generate structured response
↓
9. Optionally generate annotated image
```
The service should reject invalid or unsupported images before sending them to the model.
Potential validation criteria include:
* File type.
* Maximum file size.
* Image dimensions.
* Corrupted images.
* Unsupported formats.
## 9. Output and Explainability
The system should not return only a single number.
For example, instead of returning:
```json
{
"count": 14
}
```
it should ideally provide enough information to understand how that number was produced.
For example:
```json
{
"total_product_faces": 14,
"products": [
{
"product_id": "PRODUCT-001",
"face_count": 8,
"detections": [
{
"confidence": 0.96,
"bbox": [120, 80, 240, 310]
}
]
}
]
}
```
An annotated image showing the detected products can also be generated.
This will make it possible for users to visually verify incorrect detections and will make model improvement significantly easier.
## 10. Deployment
The service can initially be deployed as a containerized application on the company's existing server infrastructure.
A possible deployment structure is:
```text
Docker Host
│
├── Caddy
│
├── Shelf Analysis API
│
├── Computer Vision Inference Service
│
└── Supporting Services
```
Docker Compose can be used for the initial deployment.
The model should be packaged with a specific version identifier so that deployments are reproducible and previous model versions can be identified.
For example:
```text
models/
├── product-detector-v1.0
├── product-detector-v1.1
└── product-detector-v2.0
```
If inference performance eventually requires GPU acceleration, the inference container can be moved to a GPU-equipped server without changing the public API contract.
## 11. Performance Considerations
The first implementation should prioritize accuracy and correctness over maximum throughput.
Performance measurements should include:
* Average inference time per image.
* Maximum sustainable requests per second.
* CPU and RAM consumption.
* GPU utilization, if applicable.
* Average image size.
* Model loading time.
* Concurrent request behavior.
If usage increases significantly, the inference component can be scaled independently from the API layer.
For example:
```text
API
|
┌──────────┼──────────┐
↓ ↓ ↓
Inference Inference Inference
Worker 1 Worker 2 Worker 3
```
For large volumes of images, asynchronous processing and a queue-based architecture may eventually be preferable to synchronous HTTP inference.
## 12. Security
Because the service will process uploaded files, basic security controls should be implemented from the beginning.
These should include:
* Authentication for API access.
* Authorization where required.
* Maximum upload size.
* Allowed image formats.
* Input validation.
* Request rate limiting.
* Secure temporary-file handling.
* Controlled storage of uploaded images.
* Logging without exposing sensitive information.
* HTTPS through the reverse proxy.
Uploaded images should not be retained indefinitely unless there is a defined business requirement for storing them.
## 13. Monitoring and Logging
The service should record operational information such as:
* Request ID.
* Timestamp.
* Processing duration.
* Model version.
* Success/failure status.
* Number of detections.
* Error type.
For example:
```text
request_id=abc123
model=v1.2
processing_time=0.84s
detections=14
status=success
```
This will allow operational problems and model-performance issues to be investigated separately.
## 14. Evaluation Metrics
The system should be evaluated using both computer-vision metrics and business-oriented metrics.
Model-level metrics may include:
* Precision.
* Recall.
* F1 score.
* mAP.
* Detection confidence.
* False-positive rate.
* False-negative rate.
The most important business metric will ultimately be the accuracy of the product-face count.
For example:
```text
Actual: 12 faces
Predicted: 11 faces
Error: -1 face
```
Evaluation should therefore also report counting error, such as:
```text
Mean Absolute Error (MAE)
Mean Absolute Percentage Error (MAPE)
```
where appropriate.
## 15. Development Phases
### Phase 1 — Proof of Concept
Objective: determine whether the problem can be solved reliably using available shelf photographs.
Activities:
* Collect representative images.
* Define product classes.
* Annotate an initial dataset.
* Evaluate pretrained detection models.
* Train an initial model.
* Measure detection and counting accuracy.
Deliverable:
**Working model capable of detecting and counting selected products.**
### Phase 2 — API Prototype
Activities:
* Develop FastAPI service.
* Implement image upload.
* Connect the trained model.
* Return structured JSON results.
* Implement basic validation.
* Add health checks.
* Containerize the service.
Deliverable:
**Internal API that accepts an image and returns product-face counts.**
### Phase 3 — Accuracy Improvement
Activities:
* Expand the dataset.
* Identify common failure cases.
* Add difficult examples.
* Improve annotations.
* Fine-tune the model.
* Evaluate against an independent test set.
Deliverable:
**Validated model with documented performance.**
### Phase 4 — Production Deployment
Activities:
* Deploy to company infrastructure.
* Configure HTTPS and authentication.
* Add logging and monitoring.
* Establish model-version management.
* Establish backup and deployment procedures.
* Document API usage.
Deliverable:
**Production-ready internal service.**
### Phase 5 — Integration
The API can subsequently be integrated with existing company applications, dashboards, mobile applications, or reporting systems.
## 16. Risks and Limitations
The main technical risk is not the API itself but the variability of real-world shelf photographs.
A model trained only on clean and well-positioned images may perform poorly when exposed to:
* Poor lighting.
* Blurred photographs.
* Obstructed products.
* Unusual camera angles.
* Very small products.
* Visually similar products.
* New packaging.
* Products that are stacked or partially hidden.
Therefore, model performance should be treated as an iterative process rather than something that can be guaranteed from the initial prototype.
Another important consideration is product evolution. Packaging changes may require additional training data and potentially model updates.
## 17. Expected Result
At completion, the company will have an internally hosted computer-vision API capable of receiving photographs of retail shelves and automatically producing structured information about the company's visible products.
The resulting architecture will provide a foundation for future computer-vision capabilities beyond simple face counting, including:
* Product presence detection.
* Shelf-space estimation.
* Planogram compliance analysis.
* Out-of-stock detection.
* Product positioning analysis.
* Competitor-product detection.
* Automated merchandising reports.
## 18. Conclusion
The proposed system combines a REST API with a specialized computer-vision model to automate product-face counting from retail shelf photographs.
The recommended development strategy is incremental: first establish whether accurate detection is achievable with representative company data, then expose the model through an API, improve its reliability using real-world images, and finally deploy it as a monitored internal production service.
This approach limits initial infrastructure investment while creating an architecture that can later scale to larger image volumes, additional products, and more advanced retail computer-vision use cases.
