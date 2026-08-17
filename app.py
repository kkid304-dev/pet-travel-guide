from flask import Flask, render_template, request

from pet_service import search_places, REGION_CODES, CATEGORY_CODES

app = Flask(__name__)

BREED_ANSWERS = {"예": True, "아니오": False, "모름": None}


@app.route("/")
def index():
    return render_template(
        "index.html",
        regions=list(REGION_CODES.keys()),
        categories=list(CATEGORY_CODES.keys()),
    )


@app.route("/result", methods=["POST"])
def result():
    region = request.form.get("region", "")
    category = request.form.get("category", "")
    breed_answer = request.form.get("is_dangerous_breed", "모름")

    weight_raw = request.form.get("pet_weight", "")
    try:
        pet_weight = float(weight_raw)
        if pet_weight <= 0:
            raise ValueError
    except ValueError:
        return render_template(
            "index.html",
            regions=list(REGION_CODES.keys()),
            categories=list(CATEGORY_CODES.keys()),
            error="반려동물 무게는 0보다 큰 숫자로 입력해주세요.",
            region=region, category=category,
        ), 400

    is_dangerous_breed = BREED_ANSWERS.get(breed_answer)
    places, total_count, err = search_places(region, category, pet_weight, is_dangerous_breed)

    return render_template(
        "result.html",
        region=region, category=category, pet_weight=pet_weight,
        breed_answer=breed_answer, places=places, total_count=total_count, error=err,
    )


if __name__ == "__main__":
    app.run(debug=True)
