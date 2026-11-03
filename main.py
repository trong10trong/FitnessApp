import base64
from datetime import datetime, timedelta
import json
import os
import flet as ft

# Tự động nhận diện vùng nhớ hợp lệ trên iPhone (iOS Native) hoặc Windows
STORAGE_DIR = os.environ.get("FLET_APP_STORAGE_DATA", ".")
DATA_FILE = os.path.join(STORAGE_DIR, "fitness_data.json")


def main(page: ft.Page):
  page.title = "Quản Lý Calo & Thể Trạng"
  page.theme_mode = ft.ThemeMode.DARK
  page.window_width = 430
  page.window_height = 850

  # --- QUẢN LÝ DỮ LIỆU OFFLINE ---
  default_data = {
      "ingredients": {
          "Ức gà sống": {"type": "gram", "calo": 120.0, "protein": 22.5},
          "Cơm trắng": {"type": "gram", "calo": 130.0, "protein": 2.7},
          "Trứng gà": {"type": "suất", "calo": 75.0, "protein": 6.0},
          "Phở bò (tô)": {"type": "suất", "calo": 500.0, "protein": 25.0},
      },
      "body_logs": {},
      "food_logs": {},
  }

  def migrate_data(data):
    # Đảm bảo tương thích với dữ liệu cũ đã lưu trên máy
    for k, v in data.get("ingredients", {}).items():
      if "type" not in v:
        v["type"] = "gram"

    for d_str, items in list(data.get("food_logs", {}).items()):
      merged = {}
      for item in items:
        name = item["name"]
        utype = item.get("unit", "gram")
        if "amount" in item:
          amt = float(item["amount"])
        elif "grams" in item:
          amt = float(item["grams"])
          utype = "gram"
        else:
          raw = (
              str(item.get("amount_str", "0"))
              .replace("suất", "")
              .replace("g", "")
              .strip()
          )
          try:
            amt = float(raw)
          except ValueError:
            amt = 0.0
          utype = "suất" if "suất" in str(item.get("amount_str", "")) else "gram"

        key = f"{name}__{utype}"
        if key not in merged:
          merged[key] = {
              "name": name,
              "amount": amt,
              "unit": utype,
              "calo": float(item["calo"]),
              "protein": float(item["protein"]),
          }
        else:
          merged[key]["amount"] = round(merged[key]["amount"] + amt, 1)
          merged[key]["calo"] = round(merged[key]["calo"] + float(item["calo"]), 1)
          merged[key]["protein"] = round(
              merged[key]["protein"] + float(item["protein"]), 1
          )
      data["food_logs"][d_str] = list(merged.values())
    return data

  def load_data():
    if os.path.exists(DATA_FILE):
      try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
          return migrate_data(json.load(f))
      except Exception:
        pass
    stored = page.client_storage.get("fitness_app_data")
    if stored:
      try:
        return migrate_data(json.loads(stored))
      except Exception:
        pass
    return migrate_data(default_data)

  def save_data():
    try:
      with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(app_data, f, ensure_ascii=False, indent=2)
    except Exception:
      pass
    page.client_storage.set(
        "fitness_app_data", json.dumps(app_data, ensure_ascii=False)
    )

  app_data = load_data()
  current_date = [datetime.now().strftime("%Y-%m-%d")]
  temp_img_b64 = [None]

  # --- THUẬT TOÁN KẾ THỪA THỂ TRẠNG THEO LỊCH ---
  def get_active_body_stats(target_date: str):
    logs = app_data["body_logs"]
    if not logs:
      return {
          "weight": 60.0,
          "height": 165.0,
          "age": 22,
          "activity": 1.375,
          "tdee": 1950.0,
          "source_date": "Mặc định",
      }
    valid_dates = [d for d in logs.keys() if d <= target_date]
    chosen_date = max(valid_dates) if valid_dates else min(logs.keys())
    res = logs[chosen_date].copy()
    res["source_date"] = chosen_date
    return res

  def calc_tdee(weight: float, height: float, age: int, activity: float):
    bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    return round(bmr * activity, 1)

  # --- ĐIỀU KHIỂN LỊCH & CHỌN ẢNH BODY TRÊN IPHONE ---
  date_label = ft.Text(
      value=current_date[0], size=16, weight=ft.FontWeight.BOLD
  )

  def change_date(delta_days: int):
    dt = datetime.strptime(current_date[0], "%Y-%m-%d") + timedelta(
        days=delta_days
    )
    current_date[0] = dt.strftime("%Y-%m-%d")
    date_label.value = current_date[0]
    refresh_all()

  def on_date_picked(e):
    if e.control.value:
      current_date[0] = e.control.value.strftime("%Y-%m-%d")
      date_label.value = current_date[0]
      refresh_all()

  date_picker = ft.DatePicker(on_change=on_date_picked)
  page.overlay.append(date_picker)

  img_status = ft.Text("Chưa chọn ảnh", size=12, color="grey")

  def on_file_picked(e: ft.FilePickerResultEvent):
    if e.files and e.files[0].path:
      try:
        with open(e.files[0].path, "rb") as f:
          temp_img_b64[0] = base64.b64encode(f.read()).decode("utf-8")
        img_status.value = f"Đã chọn: {e.files[0].name}"
        page.update()
      except Exception as ex:
        img_status.value = f"Lỗi đọc ảnh: {ex}"
        page.update()

  file_picker = ft.FilePicker(on_result=on_file_picked)
  page.overlay.append(file_picker)

  # --- TAB 1: NHẬT KÝ ĂN UỐNG HÀNG NGÀY (TỰ ĐỘNG CỘNG DỒN) ---
  active_stats_banner = ft.Container(
      padding=10, bgcolor="bluegrey900", border_radius=8
  )
  food_dropdown = ft.Dropdown(label="Chọn nguyên liệu / món ăn", expand=True)
  food_amount_input = ft.TextField(
      label="Số g / suất", width=115, keyboard_type=ft.KeyboardType.NUMBER
  )
  daily_food_list = ft.Column(spacing=4)
  daily_summary_text = ft.Text(size=14, weight=ft.FontWeight.BOLD)

  def add_daily_food(e):
    ing_name = food_dropdown.value
    try:
      amount = float(food_amount_input.value)
    except (ValueError, TypeError):
      return
    if not ing_name or ing_name not in app_data["ingredients"] or amount <= 0:
      return

    ing_info = app_data["ingredients"][ing_name]
    item_type = ing_info.get("type", "gram")

    if item_type == "suất":
      calo = round(amount * ing_info["calo"], 1)
      protein = round(amount * ing_info["protein"], 1)
    else:
      calo = round((amount / 100.0) * ing_info["calo"], 1)
      protein = round((amount / 100.0) * ing_info["protein"], 1)

    d_str = current_date[0]
    if d_str not in app_data["food_logs"]:
      app_data["food_logs"][d_str] = []

    # Kiểm tra xem món ăn đã có trong ngày chưa để cộng dồn
    existing_item = next(
        (
            item
            for item in app_data["food_logs"][d_str]
            if item["name"] == ing_name and item.get("unit", "gram") == item_type
        ),
        None,
    )

    if existing_item:
      existing_item["amount"] = round(existing_item["amount"] + amount, 1)
      existing_item["calo"] = round(existing_item["calo"] + calo, 1)
      existing_item["protein"] = round(existing_item["protein"] + protein, 1)
    else:
      app_data["food_logs"][d_str].append({
          "name": ing_name,
          "amount": round(amount, 1),
          "unit": item_type,
          "calo": calo,
          "protein": protein,
      })

    food_amount_input.value = ""
    save_data()
    refresh_all()

  def delete_food_item(d_str, idx):
    app_data["food_logs"][d_str].pop(idx)
    if not app_data["food_logs"][d_str]:
      del app_data["food_logs"][d_str]
    save_data()
    refresh_all()

  # --- TAB 2: NHẬP LIỆU NGUYÊN LIỆU & THỂ TRẠNG ---
  ing_name_in = ft.TextField(label="Tên nguyên liệu / món ăn", expand=True)
  ing_type_dropdown = ft.Dropdown(
      label="Đơn vị tính",
      value="gram",
      options=[
          ft.dropdown.Option("gram", "Theo 100g"),
          ft.dropdown.Option("suất", "Theo 1 suất"),
      ],
      width=145,
  )
  ing_calo_in = ft.TextField(
      label="Calo", width=105, keyboard_type=ft.KeyboardType.NUMBER
  )
  ing_prot_in = ft.TextField(
      label="Protein", width=105, keyboard_type=ft.KeyboardType.NUMBER
  )
  ing_list_view = ft.Column(spacing=4)

  def save_ingredient(e):
    name = ing_name_in.value.strip()
    itype = ing_type_dropdown.value
    try:
      c = float(ing_calo_in.value)
      p = float(ing_prot_in.value)
    except (ValueError, TypeError):
      return
    if name:
      app_data["ingredients"][name] = {"type": itype, "calo": c, "protein": p}
      ing_name_in.value = ""
      ing_calo_in.value = ""
      ing_prot_in.value = ""
      save_data()
      refresh_all()

  def delete_ingredient(name):
    if name in app_data["ingredients"]:
      del app_data["ingredients"][name]
      save_data()
      refresh_all()

  weight_in = ft.TextField(
      label="Nặng (kg)", width=110, keyboard_type=ft.KeyboardType.NUMBER
  )
  height_in = ft.TextField(
      label="Cao (cm)",
      value="165",
      width=110,
      keyboard_type=ft.KeyboardType.NUMBER,
  )
  age_in = ft.TextField(
      label="Tuổi", value="22", width=80, keyboard_type=ft.KeyboardType.NUMBER
  )
  activity_in = ft.Dropdown(
      label="Mức vận động",
      value="1.375",
      options=[
          ft.dropdown.Option("1.2", "Ít vận động (1.2)"),
          ft.dropdown.Option("1.375", "Tập 3 buổi/tuần (1.375)"),
          ft.dropdown.Option("1.55", "Tập 4-5 buổi/tuần (1.55)"),
          ft.dropdown.Option("1.725", "Vận động nặng (1.725)"),
      ],
  )

  def save_body_stats(e):
    try:
      w = float(weight_in.value)
      h = float(height_in.value)
      a = int(age_in.value)
      act = float(activity_in.value)
    except (ValueError, TypeError):
      return
    tdee_val = calc_tdee(w, h, a, act)
    app_data["body_logs"][current_date[0]] = {
        "weight": w,
        "height": h,
        "age": a,
        "activity": act,
        "tdee": tdee_val,
        "img_b64": temp_img_b64[0],
    }
    temp_img_b64[0] = None
    img_status.value = "Đã lưu mốc thể trạng!"
    save_data()
    refresh_all()

  # --- TAB 3: THỐNG KÊ BẢNG & BIỂU ĐỒ ---
  total_deficit_banner = ft.Container(
      padding=10, bgcolor="teal900", border_radius=8
  )
  calo_table = ft.DataTable(
      column_spacing=12,
      columns=[
          ft.DataColumn(ft.Text("Ngày")),
          ft.DataColumn(ft.Text("Nạp")),
          ft.DataColumn(ft.Text("Pro")),
          ft.DataColumn(ft.Text("TDEE")),
          ft.DataColumn(ft.Text("Hao hụt")),
      ],
      rows=[],
  )
  body_table = ft.DataTable(
      column_spacing=12,
      columns=[
          ft.DataColumn(ft.Text("Mốc")),
          ft.DataColumn(ft.Text("Kg")),
          ft.DataColumn(ft.Text("Cm")),
          ft.DataColumn(ft.Text("TDEE")),
          ft.DataColumn(ft.Text("Ảnh")),
      ],
      rows=[],
  )
  weight_chart_container = ft.Container(
      height=240, padding=ft.padding.only(top=15, right=20, left=5, bottom=5)
  )

  def show_body_image(b64_str, d_str):
    dlg = ft.AlertDialog(
        title=ft.Text(f"Body ngày {d_str}"),
        content=ft.Image(
            src_base64=b64_str, width=260, height=340, fit=ft.ImageFit.CONTAIN
        ),
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()

  # --- CẬP NHẬT GIAO DIỆN ĐỒNG BỘ ---
  def refresh_all():
    d_str = current_date[0]
    active_body = get_active_body_stats(d_str)

    active_stats_banner.content = ft.Column([
        ft.Text(
            f"Thể trạng áp dụng (Mốc: {active_body['source_date']})",
            size=12,
            color="amber",
        ),
        ft.Text(
            f"Nặng: {active_body['weight']}kg | Cao: {active_body['height']}cm | TDEE: {active_body['tdee']} kcal",
            weight=ft.FontWeight.BOLD,
            size=13,
        ),
    ])

    food_dropdown.options = [
        ft.dropdown.Option(k) for k in sorted(app_data["ingredients"].keys())
    ]

    daily_food_list.controls.clear()
    day_foods = app_data["food_logs"].get(d_str, [])
    total_c = sum(item["calo"] for item in day_foods)
    total_p = sum(item["protein"] for item in day_foods)
    day_deficit = round(active_body["tdee"] - total_c, 1)

    for idx, item in enumerate(day_foods):
      unit_str = (
          f"{item['amount']} suất"
          if item.get("unit") == "suất"
          else f"{item['amount']}g"
      )
      daily_food_list.controls.append(
          ft.Row(
              alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
              controls=[
                  ft.Text(
                      f"• {item['name']} ({unit_str}): {item['calo']} kcal | {item['protein']}g P",
                      size=13,
                      expand=True,
                  ),
                  ft.TextButton(
                      "Xóa",
                      on_click=lambda e, i=idx: delete_food_item(d_str, i),
                  ),
              ],
          )
      )

    daily_summary_text.value = (
        f"Tổng nạp: {round(total_c, 1)} kcal | Protein: {round(total_p, 1)}g\n"
        f"Hao hụt trong ngày: {day_deficit} kcal"
    )

    ing_list_view.controls.clear()
    for k, v in app_data["ingredients"].items():
      itype = v.get("type", "gram")
      unit_label = "100g" if itype == "gram" else "suất"
      ing_list_view.controls.append(
          ft.Row(
              alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
              controls=[
                  ft.Text(
                      f"• {k}: {v['calo']} kcal/{unit_label} | {v['protein']}g P/{unit_label}",
                      size=12,
                      expand=True,
                  ),
                  ft.TextButton(
                      "Xóa",
                      on_click=lambda e, name=k: delete_ingredient(name),
                  ),
              ],
          )
      )

    calo_table.rows.clear()
    cumulative_deficit = 0.0
    for log_date in sorted(app_data["food_logs"].keys(), reverse=True):
      items = app_data["food_logs"][log_date]
      c_in = round(sum(i["calo"] for i in items), 1)
      p_in = round(sum(i["protein"] for i in items), 1)
      st = get_active_body_stats(log_date)
      def_val = round(st["tdee"] - c_in, 1)
      cumulative_deficit += def_val
      calo_table.rows.append(
          ft.DataRow(
              cells=[
                  ft.DataCell(ft.Text(log_date[5:])),
                  ft.DataCell(ft.Text(str(c_in))),
                  ft.DataCell(ft.Text(str(p_in))),
                  ft.DataCell(ft.Text(str(st["tdee"]))),
                  ft.DataCell(
                      ft.Text(
                          str(def_val),
                          color="green" if def_val >= 0 else "red",
                      )
                  ),
              ]
          )
      )

    est_fat_loss = round(cumulative_deficit / 7700.0, 2)
    total_deficit_banner.content = ft.Column([
        ft.Text(
            f"Tổng hao hụt tích lũy: {round(cumulative_deficit, 1)} kcal",
            size=15,
            weight=ft.FontWeight.BOLD,
        ),
        ft.Text(f"Giảm mỡ ước tính: ~{est_fat_loss} kg", size=12),
    ])

    body_table.rows.clear()
    sorted_b_dates = sorted(app_data["body_logs"].keys())
    chart_points = []
    bottom_labels = []

    # Hiển thị tối đa 6 nhãn ngày trên trục ngang để không bị đè chữ
    step = max(1, len(sorted_b_dates) // 5)

    for idx, b_date in enumerate(sorted_b_dates):
      b_info = app_data["body_logs"][b_date]
      w_val = b_info["weight"]
      short_date = b_date[5:]  # Định dạng MM-DD

      chart_points.append(
          ft.LineChartDataPoint(
              idx,
              w_val,
              tooltip=f"Ngày {short_date}\n{w_val} kg",
              show_above_line=True,
          )
      )

      if idx % step == 0 or idx == len(sorted_b_dates) - 1:
        bottom_labels.append(
            ft.ChartAxisLabel(
                value=idx,
                label=ft.Container(
                    ft.Text(short_date, size=10, color="grey300"),
                    padding=ft.padding.only(top=5),
                ),
            )
        )

      img_btn = (
          ft.TextButton(
              "Xem",
              on_click=lambda e, b=b_info["img_b64"], d=b_date: show_body_image(
                  b, d
              ),
          )
          if b_info.get("img_b64")
          else ft.Text("-")
      )
      body_table.rows.append(
          ft.DataRow(
              cells=[
                  ft.DataCell(ft.Text(short_date)),
                  ft.DataCell(ft.Text(str(w_val))),
                  ft.DataCell(ft.Text(str(b_info["height"]))),
                  ft.DataCell(ft.Text(str(b_info["tdee"]))),
                  ft.DataCell(img_btn),
              ]
          )
      )

    if chart_points:
      weights = [app_data["body_logs"][d]["weight"] for d in sorted_b_dates]
      min_w = int(min(weights)) - 2
      max_w = int(max(weights)) + 2
      y_step = max(1, (max_w - min_w) // 4)

      left_labels = [
          ft.ChartAxisLabel(
              value=val,
              label=ft.Text(f"{val}kg", size=10, color="grey300"),
          )
          for val in range(min_w, max_w + 1, y_step)
      ]

      weight_chart_container.content = ft.LineChart(
          data_series=[
              ft.LineChartData(
                  data_points=chart_points,
                  stroke_width=3,
                  color="cyan",
                  curved=True,
                  point=True,
              )
          ],
          min_y=min_w,
          max_y=max_w,
          min_x=0,
          max_x=max(1, len(sorted_b_dates) - 1),
          left_axis=ft.ChartAxis(labels=left_labels, labels_size=40),
          bottom_axis=ft.ChartAxis(labels=bottom_labels, labels_size=28),
          horizontal_grid_lines=ft.ChartGridLines(
              interval=y_step, color="grey800", width=1
          ),
          tooltip_bgcolor="bluegrey900",
          border=ft.border.all(1, "grey800"),
          expand=True,
      )
    else:
      weight_chart_container.content = ft.Text(
          "Chưa có dữ liệu mốc cân nặng.", color="grey"
      )

    page.update()

  # --- THANH LỊCH CÂN XỨNG HAI BÊN & BỐ CỤC CHÍNH ---
  calendar_bar = ft.Container(
      padding=ft.padding.symmetric(vertical=4, horizontal=4),
      content=ft.Row(
          alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
          vertical_alignment=ft.CrossAxisAlignment.CENTER,
          controls=[
              ft.ElevatedButton(
                  "<",
                  width=48,
                  height=38,
                  on_click=lambda e: change_date(-1),
              ),
              ft.Row(
                  spacing=10,
                  vertical_alignment=ft.CrossAxisAlignment.CENTER,
                  controls=[
                      date_label,
                      ft.ElevatedButton(
                          "Lịch",
                          height=38,
                          on_click=lambda e: page.open(date_picker),
                      ),
                  ],
              ),
              ft.ElevatedButton(
                  ">",
                  width=48,
                  height=38,
                  on_click=lambda e: change_date(1),
              ),
          ],
      ),
  )

  tabs = ft.Tabs(
      selected_index=0,
      expand=True,
      tabs=[
          ft.Tab(
              text="Ăn uống",
              content=ft.Column(
                  scroll=ft.ScrollMode.AUTO,
                  controls=[
                      active_stats_banner,
                      ft.Row([food_dropdown, food_amount_input]),
                      ft.ElevatedButton(
                          "Thêm món ăn", on_click=add_daily_food
                      ),
                      daily_summary_text,
                      daily_food_list,
                  ],
              ),
          ),
          ft.Tab(
              text="Nhập liệu",
              content=ft.Column(
                  scroll=ft.ScrollMode.AUTO,
                  controls=[
                      ft.Text(
                          "1. Cập nhật Thể trạng (Từ ngày đang chọn)",
                          weight=ft.FontWeight.BOLD,
                      ),
                      ft.Row([weight_in, height_in, age_in]),
                      activity_in,
                      ft.Row([
                          ft.ElevatedButton(
                              "Chọn ảnh Body",
                              on_click=lambda _: file_picker.pick_files(
                                  allow_multiple=False,
                                  file_type=ft.FilePickerFileType.IMAGE,
                              ),
                          ),
                          img_status,
                      ]),
                      ft.ElevatedButton(
                          "Lưu Thể trạng & Tính TDEE", on_click=save_body_stats
                      ),
                      ft.Text(
                          "2. Thêm Nguyên liệu / Món ăn sẵn",
                          weight=ft.FontWeight.BOLD,
                      ),
                      ing_name_in,
                      ft.Row([ing_type_dropdown, ing_calo_in, ing_prot_in]),
                      ft.ElevatedButton(
                          "Lưu Nguyên liệu / Món", on_click=save_ingredient
                      ),
                      ing_list_view,
                  ],
              ),
          ),
          ft.Tab(
              text="Thống kê",
              content=ft.Column(
                  scroll=ft.ScrollMode.AUTO,
                  controls=[
                      total_deficit_banner,
                      ft.Text(
                          "Biểu đồ cân nặng (Chạm vào điểm để xem chi tiết)",
                          weight=ft.FontWeight.BOLD,
                      ),
                      weight_chart_container,
                      ft.Text(
                          "Bảng calo từng ngày", weight=ft.FontWeight.BOLD
                      ),
                      ft.Row([calo_table], scroll=ft.ScrollMode.AUTO),
                      ft.Text(
                          "Bảng thể trạng theo mốc", weight=ft.FontWeight.BOLD
                      ),
                      ft.Row([body_table], scroll=ft.ScrollMode.AUTO),
                  ],
              ),
          ),
      ],
  )

  page.add(
      ft.SafeArea(
          ft.Column([calendar_bar, tabs], expand=True),
          expand=True,
      )
  )
  refresh_all()


ft.app(target=main)
