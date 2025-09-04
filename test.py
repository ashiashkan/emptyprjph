def buy_medicine(request: HttpRequest):
    lang = get_language()[:2]

    # فیلتر جستجو
    query = request.GET.get("q", "").strip()
    groups = []
    for gkey in _GROUPS_RAW.keys():
        loc_group = localize_group(gkey, lang)
        if loc_group:
            if query:
                if any(query.lower() in v.name.lower() for v in loc_group.variants):
                    groups.append(loc_group)
            else:
                groups.append(loc_group)

    # دیگه صفحه‌بندی نمی‌کنیم → همه گروه‌ها یکجا
    context = {
        "groups": groups,
        "query": query,
    }
    return render(request, "buy_medicine.html", context)
