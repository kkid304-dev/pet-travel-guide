from flask import Flask, render_template, request

from pet_service import search_places, get_sigungu_codes, warm_sigungu_cache, REGION_CODES, CATEGORY_CODES

app = Flask(__name__)

BREED_ANSWERS = {"예": True, "아니오": False, "모름": None}

warm_sigungu_cache()


@app.route("/")
def index():
    sigungu_by_region = {region: get_sigungu_codes(region) for region in REGION_CODES}
    return render_template(
        "index.html",
        regions=list(REGION_CODES.keys()),
        categories=list(CATEGORY_CODES.keys()),
        sigungu_by_region=sigungu_by_region,
    )


@app.route("/result", methods=["POST"])
def result():
    region = request.form.get("region", "")
    category = request.form.get("category", "")
    sigungu_code = request.form.get("sigungu", "")
    keyword = request.form.get("keyword", "").strip()
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
            sigungu_by_region={region: get_sigungu_codes(region) for region in REGION_CODES},
            error="반려동물 무게는 0보다 큰 숫자로 입력해주세요.",
            region=region, category=category,
        ), 400

    is_dangerous_breed = BREED_ANSWERS.get(breed_answer)
    places, total_count, err = search_places(
        region, category, pet_weight, is_dangerous_breed, sigungu_code=sigungu_code, keyword=keyword,
    )

    return render_template(
        "result.html",
        region=region, category=category, pet_weight=pet_weight, sigungu_code=sigungu_code, keyword=keyword,
        breed_answer=breed_answer, places=places, total_count=total_count, error=err,
    )


@app.route("/more")
def more():
    region = request.args.get("region", "")
    category = request.args.get("category", "")
    sigungu_code = request.args.get("sigungu", "")
    keyword = request.args.get("keyword", "").strip()
    breed_answer = request.args.get("breed_answer", "모름")

    try:
        pet_weight = float(request.args.get("pet_weight", ""))
        page = int(request.args.get("page", ""))
        if pet_weight <= 0 or page < 1:
            raise ValueError
    except ValueError:
        return {"html": "", "count": 0}, 400

    is_dangerous_breed = BREED_ANSWERS.get(breed_answer)
    places, total_count, err = search_places(
        region, category, pet_weight, is_dangerous_breed, page=page, sigungu_code=sigungu_code, keyword=keyword,
    )
    if err:
        return {"html": "", "count": 0}, 502

    return {"html": render_template("_place_cards.html", places=places), "count": len(places)}


if __name__ == "__main__":
    app.run(debug=True)
