"""Cấu hình tập trung các định danh step và template dùng chung trong ứng dụng."""

# Template dùng trong quy trình đăng nhập và xác minh tài khoản.
_TEMPLATE_ACCOUNT_DICH_QUAN_TAP_KICH = "accounts10/dich_quan_tap_kich"
_TEMPLATE_ACCOUNT_WAITING = "accounts1/waiting"
_TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN = "accounts9/cap_nhat_thong_tin"
_TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN = "accounts9/close_cap_nhat_thong_tin"
_TEMPLATE_ACCOUNT_MAN_HINH_CHINH = "accounts2/man_hinh_chinh"
_TEMPLATE_ACCOUNT_THONG_TIN_DANG_NHAP_KHONG_DUNG = "accounts4/thong_tin_dang_nhap_khong_dung"
_TEMPLATE_ACCOUNT_TRANG_CA_NHAN = "accounts5/trang_ca_nhan"
_TEMPLATE_ACCOUNT_DANG_NHAP = "accounts3/dang_nhap"

# Step được chọn từ cấu hình tác vụ.
_STEP_QUOC_VAN = "hoat_dong_phuc_loi_le_bao_quoc_van"
_STEP_DIEM_DANH = "hoat_dong_phuc_loi_diem_danh"


_STEP_QUAN_DOAN_BAO_DANH = "quan_doan_bao_danh"
_STEP_QUAN_DOAN_TUI_PHUC = "quan_doan_tui_phuc"
_STEP_QUAN_DOAN_CAU_VAN = "quan_doan_cau_van"
_STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO = "quan_doan_dong_gop_luong_thao"
_STEP_QUAN_DOAN_DONG_GOP_KNB = "quan_doan_dong_gop_knb"

# Template dùng để mở và đóng màn hình Quân đoàn.
_TEMPLATE_MAIN_QUAN_DOAN_MO_CHAT = "main/quan_doan_mo_chat"
_TEMPLATE_QUAN_DOAN_CHAT_VAO_QUAN_DOAN = "quan_doan.chat/vao_quan_doan"
_TEMPLATE_QUAN_DOAN_CHAT_TAT_CHAT = "quan_doan.chat/quan_doan_tat_chat"

# Template dùng để nhận diện trạng thái bên trong màn hình Quân đoàn.
_TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH = "quan_doan/quan_doan_man_hinh_chinh"
_TEMPLATE_QUAN_DOAN_CAU_VAN = "quan_doan/quan_doan_cau_van"
_TEMPLATE_QUAN_DOAN_LANH_DIA_CHIEN = "quan_doan/quan_doan_lanh_dia_chien"
_TEMPLATE_QUAN_DOAN_CHUA_NHAN_TUI_PHUC = "quan_doan/quan_doan_chua_nhan_tui_phuc"
_TEMPLATE_QUAN_DOAN_DA_NHAN_TUI_PHUC = "quan_doan/quan_doan_da_nhan_tui_phuc"
_TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH = "quan_doan/quan_doan_chua_bao_danh"
_TEMPLATE_QUAN_DOAN_DA_BAO_DANH = "quan_doan/quan_doan_da_bao_danh"
_TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO = "quan_doan/quan_doan_chua_dong_gop_luong_thao"
_TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO = "quan_doan/quan_doan_da_dong_gop_luong_thao"
_TEMPLATE_QUAN_DOAN_DONG_GOP_KNB = "quan_doan/quan_doan_dong_gop_knb"

# Template dùng bên trong màn hình Cầu vận Quân đoàn.
_TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN = "quan_doan.cau_van/quan_doan_man_hinh_cau_van"
_TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN = "quan_doan.cau_van/quan_doan_co_the_cau_van"
_TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1 = "quan_doan.cau_van/quan_doan_het_luot_cau_van1"
_TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2 = "quan_doan.cau_van/quan_doan_het_luot_cau_van2"

# Template dùng bên trong màn hình đóng góp Lương thảo Quân đoàn.
_TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO      = "quan_doan.luong_thao/quan_doan_man_hinh_dong_gop_luong_thao"
_TEMPLATE_QUAN_DOAN_DUNG_NHANH = "quan_doan.luong_thao/dung_nhanh"
_TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO = "quan_doan.luong_thao/dong_man_hinh_dong_gop_luong_thao"
_TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB = "quan_doan.luong_thao/lay_them_luong_thao_KNB"

# Template dùng bên trong màn hình đóng góp KNB Quân đoàn.
_TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_KNB = "quan_doan.knb/quan_doan_man_hinh_dong_gop_knb"
_TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB = "quan_doan.knb/quan_doan_dong_gop_10_knb"
_TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB = "quan_doan.knb/quan_doan_dong_gop_20_knb"
_TEMPLATE_QUAN_DOAN_DONG_GOP_40_KNB = "quan_doan.knb/quan_doan_dong_gop_40_knb"

# Template dùng bên trong màn hình nhận túi phúc.
_TEMPLATE_QUAN_DOAN_MAN_HINH_NHAN_TUI_PHUC = "quan_doan.tui_phuc/man_hinh_nhan_tui_phuc"
_TEMPLATE_QUAN_DOAN_TUI_PHUC_CHI_TIET = "quan_doan.tui_phuc/chi_tiet"

# Template dùng để điều hướng trong màn hình Hoạt động - Phúc lợi.
_TEMPLATE_MAIN_HOAT_DONG = "main/hoat_dong"
_TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN = "hoat_dong.phuc_loi/dang_chon_le_bao_quoc_van"
_TEMPLATE_CHUA_CHON_LE_BAO_QUOC_VAN = "hoat_dong.phuc_loi/chua_chon_le_bao_quoc_van"
_TEMPLATE_DANG_CHON_DIEM_DANH = "hoat_dong.phuc_loi/dang_chon_diem_danh"
_TEMPLATE_CHUA_CHON_DIEM_DANH = "hoat_dong.phuc_loi/chua_chon_diem_danh"
_TEMPLATE_DANG_CHON_PHUC_LOI = "hoat_dong/dang_chon_phuc_loi"
_TEMPLATE_CHUA_CHON_PHUC_LOI = "hoat_dong/chua_chon_phuc_loi"
_TEMPLATE_DANG_CHON_HOAT_DONG = "hoat_dong/dang_chon_hoat_dong"
_TEMPLATE_CHUA_CHON_HOAT_DONG = "hoat_dong/chua_chon_hoat_dong"

# Template dùng bên trong tác vụ Điểm danh.
_TEMPLATE_NGAY_CAN_DIEM_DANH = "hoat_dong/ngay_can_diem_danh"
_TEMPLATE_XAC_NHAN_DIEM_DANH_BU = "hoat_dong/xac_nhan_diem_danh_bu"

# Template dùng bên trong tác vụ nhận lễ bao Quốc Vận.
_TEMPLATE_NHAN_LE_BAO_MIEN_PHI = "hoat_dong/nhan_le_bao_mien_phi"
_TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI = "hoat_dong/da_nhan_le_bao_mien_phi"
