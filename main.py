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
          "Ức gà sống": {"calo": 120.0, "protein": 22.5},
          "Cơm trắng": {"calo": 130.0, "protein": 2.7},
          "Trứng gà": {"calo": 155.0, "protein": 13.0},
          "Thịt bò thăn": {"calo": 143.0, "protein": 22.0},
      },
      "body_logs": {},
      "food_logs": {},
  }

  def load_data():
    if os.path.exists(DATA_FILE):
      try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
          return json.load(f)
      except Exception:
        pass
    stored = page.client_storage.get("fitness_app_data")
    return json.loads(stored) if stored else default_data

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

  # --- TAB 1: NHẬT KÝ ĂN UỐNG HÀNG NGÀY ---
  active_stats_banner = ft.Container(
      padding=10, bgcolor="bluegrey900", border_radius=8
  )
  food_dropdown = ft.Dropdown(label="Chọn nguyên liệu", expand=True)
  food_grams_input = ft.TextField(
      label="Số g", width=100, keyboard_type=ft.KeyboardType.NUMBER
  )
  daily_food_list = ft.Column(spacing=4)
  daily_summary_text = ft.Text(size=14, weight=ft.FontWeight.BOLD)

  def add_daily_food(e):
    ing_name = food_dropdown.value
    try:
      grams = float(food_grams_input.value)
    except (ValueError, TypeError):
      return
    if not ing_name or ing_name not in app_data["ingredients"]:
      return

    ing_info = app_data["ingredients"][ing_name]
    calo = round((grams / 100.0) * ing_info["calo"], 1)
    protein = round((grams / 100.0) * ing_info["protein"], 1)

    d_str = current_date[0]
    if d_str not in app_data["food_logs"]:
      app_data["food_logs"][d_str] = []
    app_data["food_logs"][d_str].append({
        "name": ing_name,
        "grams": grams,
        "calo": calo,
        "protein": protein,
    })
    food_grams_input.value = ""
    save_data()
    refresh_all()

  def delete_food_item(d_str, idx):
    app_data["food_logs"][d_str].pop(idx)
    if not app_data["food_logs"][d_str]:
      del app_data["food_logs"][d_str]
    save_data()
    refresh_all()

  # --- TAB 2: NHẬP LIỆU NGUYÊN LIỆU & THỂ TRẠNG ---
  ing_name_in = ft.TextField(label="Tên nguyên liệu", expand=True)
  ing_calo_in = ft.TextField(
      label="Calo/100g", width=120, keyboard_type=ft.KeyboardType.NUMBER
  )
  ing_prot_in = ft.TextField(
      label="Protein/100g", width=120, keyboard_type=ft.KeyboardType.NUMBER
  )
  ing_list_view = ft.Column(spacing=4)

  def save_ingredient(e):
    name = ing_name_in.value.strip()
    try:
      c = float(ing_calo_in.value)
      p = float(ing_prot_in.value)
    except (ValueError, TypeError):
      return
    if name:
      app_data["ingredients"][name] = {"calo": c, "protein": p}
      ing_name_in.value = ""
      ing_calo_in.value = ""
      ing_prot_in.value = ""
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
  weight_chart_container = ft.Container(height=200, padding=10)

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
      daily_food_list.controls.append(
          ft.Row(
              alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
              controls=[
                  ft.Text(
                      f"• {item['name']} ({item['grams']}g): {item['calo']} kcal | {item['protein']}g P",
                      size=13,
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
      ing_list_view.controls.append(
          ft.Text(
              f"• {k}: {v['calo']} kcal/100g | {v['protein']}g P/100g", size=12
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

    for idx, b_date in enumerate(sorted_b_dates):
      b_info = app_data["body_logs"][b_date]
      chart_points.append(ft.LineChartDataPoint(idx, b_info["weight"]))
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
                  ft.DataCell(ft.Text(b_date[5:])),
                  ft.DataCell(ft.Text(str(b_info["weight"]))),
                  ft.DataCell(ft.Text(str(b_info["height"]))),
                  ft.DataCell(ft.Text(str(b_info["tdee"]))),
                  ft.DataCell(img_btn),
              ]
          )
      )

    if chart_points:
      weights = [app_data["body_logs"][d]["weight"] for d in sorted_b_dates]
      weight_chart_container.content = ft.LineChart(
          data_series=[
              ft.LineChartData(
                  data_points=chart_points,
                  stroke_width=3,
                  color="cyan",
                  curved=True,
              )
          ],
          min_y=min(weights) - 2,
          max_y=max(weights) + 2,
          border=ft.border.all(1, "grey800"),
          expand=True,
      )
    else:
      weight_chart_container.content = ft.Text(
          "Chưa có dữ liệu mốc cân nặng.", color="grey"
      )

    page.update()

  # --- THANH LỊCH & BỐ CỤC CHÍNH ---
  calendar_bar = ft.Row(
      alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
      controls=[
          ft.ElevatedButton("<", width=45, on_click=lambda e: change_date(-1)),
          date_label,
          ft.ElevatedButton(
              "Lịch", on_click=lambda e: page.open(date_picker)
          ),
          ft.ElevatedButton(">", width=45, on_click=lambda e: change_date(1)),
      ],
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
                      ft.Row([food_dropdown, food_grams_input]),
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
                          "2. Thêm Nguyên liệu mới", weight=ft.FontWeight.BOLD
                      ),
                      ing_name_in,
                      ft.Row([ing_calo_in, ing_prot_in]),
                      ft.ElevatedButton(
                          "Lưu Nguyên liệu", on_click=save_ingredient
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
                          "Biểu đồ cân nặng", weight=ft.FontWeight.BOLD
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