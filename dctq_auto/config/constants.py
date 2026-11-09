"""Cấu hình tập trung các định danh step và template dùng chung trong ứng dụng."""

# Template dùng trong quy trình đăng nhập và xác minh tài khoản.
_TEMPLATE_THONG_BAO_DICH_QUAN_TAP_KICH = "main.dich_quan_tap_kich/thong_bao_bi_tan_cong"
_TEMPLATE_ACCOUNT_WAITING = "accounts1/waiting"
_TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN = "accounts9/cap_nhat_thong_tin"
_TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN = "accounts9/close_cap_nhat_thong_tin"
_TEMPLATE_ACCOUNT_MAN_HINH_CHINH = "accounts2/man_hinh_chinh"
_TEMPLATE_ACCOUNT_THONG_TIN_DANG_NHAP_KHONG_DUNG = "accounts4/thong_tin_dang_nhap_khong_dung"
_TEMPLATE_ACCOUNT_TRANG_CA_NHAN = "accounts5/trang_ca_nhan"
_TEMPLATE_ACCOUNT_DANG_NHAP = "accounts3/dang_nhap"

# Template màn hình đã biết
_TEMPLATE_MAIN_SU_KIEN_TANG_QUA_HANG_NGAY = "main.su_kien/tang_qua_hang_ngay"
_TEMPLATE_MAIN_SU_KIEN_AN_CHO_TRONG_DE_THOAT = "main.su_kien/an_cho_trong_de_thoat"

# Step được chọn từ cấu hình tác vụ.
_STEP_NHAN_THUONG_TAM_QUOC_LENH = "hoat_dong_nhan_thuong_tam_quoc_lenh"
_STEP_NHAN_THUONG_NHIEM_VU_HANG_NGAY = "hoat_dong_nhan_thuong_nhiem_vu_hang_ngay"
_STEP_QUOC_VAN = "hoat_dong_phuc_loi_le_bao_quoc_van"
_STEP_DIEM_DANH = "hoat_dong_phuc_loi_diem_danh"
_STEP_QUAN_SU_GIAO_TRANH = "quan_su_giao_tranh"


# Step và template dùng trong quy trình Tranh Bá.
_STEP_QUAN_SU_TRANH_BA = "quan_su_tranh_ba"
_TEMPLATE_QUAN_SU_TRANH_BA_LOI_VAO = "quan_su.tranh_ba/loi_vao_tranh_ba"
_TEMPLATE_QUAN_SU_TRANH_BA_TIM_DOI_THU = "quan_su.tranh_ba/tim_doi_thu"
_TEMPLATE_QUAN_SU_TRANH_BA_XUAT_CHIEN = "quan_su.tranh_ba/xuat_chien"
_TEMPLATE_QUAN_SU_TRANH_BA_CHUA_CO_CHIEN_THUAT = "quan_su.tranh_ba/chua_co_chien_thuat"
_TEMPLATE_QUAN_SU_TRANH_BA_RUT_LUI = "quan_su.tranh_ba/rut_lui"
_TEMPLATE_QUAN_SU_TRANH_BA_THU_QUAN = "quan_su.tranh_ba/thu_quan"
_TEMPLATE_QUAN_SU_TRANH_BA_HOP_THOAI_THU_QUAN = "quan_su.tranh_ba/hop_thoai_thu_quan"
_TEMPLATE_QUAN_SU_TRANH_BA_TRAN_SAU = "quan_su.tranh_ba/tran_sau"
_TEMPLATE_QUAN_SU_TRANH_BA_HOI_THANH = "quan_su.tranh_ba/hoi_thanh"
_TEMPLATE_QUAN_SU_TRANH_BA_MUA_THE_LUC = "quan_su.tranh_ba/mua_the_luc"

# Step và template dùng trong quy trình Chiến Tranh.
_STEP_CHIEN_TRANH_MUU_BINH = "chien_tranh_muu_binh"
_STEP_CHIEN_TRANH_QUOC_CHIEN = "chien_tranh_quoc_chien"
_STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG = "chien_tranh_quan_doan_nhan_thuong"

_TEMPLATE_MAIN_CHIEN_TRANH = "main/chien_tranh"
_TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH = "chien_tranh/man_hinh_chinh"
_TEMPLATE_CHIEN_TRANH_MUU_BINH = "chien_tranh/muu_binh"

# Template dùng trong quy trình nhận thưởng Đoàn Chiến.
_TEMPLATE_CHIEN_TRANH2_DOAN_CHIEN = "chien_tranh2/doan_chien"
_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_MAN_HINH_CHINH = "chien_tranh.doan_chien/man_hinh_chinh"
_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_MAN_HINH = "chien_tranh.doan_chien/dong_man_hinh_doan_chien"
_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DA_NHAN_THUONG = "chien_tranh.doan_chien/da_nhan_thuong"
_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_CHUA_NHAN_THUONG = "chien_tranh.doan_chien/chua_nhan_thuong"
_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_NHAN_THUONG = "chien_tranh.doan_chien/an_cho_trong_de_nhan_thuong"
_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_THOAT = "chien_tranh.doan_chien/an_cho_trong_de_thoat"
_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_TONG_KET = "chien_tranh.doan_chien/tong_ket_doan_chien"
_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET = "chien_tranh.doan_chien/dong_tong_ket_doan_chien"

# Template dùng trong quy trình nhận thưởng Tam Quốc Lệnh.
_TEMPLATE_MAIN_TAM_QUOC_LENH = "main/tam_quoc_lenh"
_TEMPLATE_TAM_QUOC_LENH_MAN_HINH_CHINH = "tam_quoc_lenh/man_hinh_chinh"
_TEMPLATE_TAM_QUOC_LENH_CHUA_MO_CHIEN_TRANH = "tam_quoc_lenh/chua_mo_chien_tranh"
_TEMPLATE_TAM_QUOC_LENH_DANG_MO_CHIEN_TRANH = "tam_quoc_lenh/dang_mo_chien_tranh"
_TEMPLATE_TAM_QUOC_LENH_CHUA_NHAN_THUONG = "tam_quoc_lenh/chua_nhan_thuong"
_TEMPLATE_TAM_QUOC_LENH_DA_NHAN_THUONG = "tam_quoc_lenh/da_nhan_thuong"
_TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH = "tam_quoc_lenh/nhan_thuong_nhanh"

# Template dùng trong quy trình Mưu Binh.
_TEMPLATE_MUU_BINH_MAN_HINH_CHINH = "chien_tranh.muu_binh/man_hinh_chinh"
_TEMPLATE_MUU_BINH_BAT_DAU = "chien_tranh.muu_binh/bat_dau"
_TEMPLATE_MUU_BINH_CHIEN_DAU = "chien_tranh.muu_binh/chien_dau"
_TEMPLATE_MUU_BINH_TU_DONG_DEN_AI_TIEP_THEO = "chien_tranh.muu_binh/tu_dong_den_ai_tiep_theo"
_TEMPLATE_MUU_BINH_RUT_LUI = "chien_tranh.muu_binh/rut_lui"
_TEMPLATE_MUU_BINH_HOI_THANH = "chien_tranh.muu_binh/hoi_thanh"
_TEMPLATE_MUU_BINH_HOP_THOAI_THUONG_VUOT_AI = "chien_tranh.muu_binh/hop_thoai_thuong_vuot_ai"
_TEMPLATE_MUU_BINH_THUONG_VUOT_AI_1 = "chien_tranh.thuong_vuot_ai/thuong_vuot_ai_1"
_TEMPLATE_MUU_BINH_THUONG_VUOT_AI_2 = "chien_tranh.thuong_vuot_ai/thuong_vuot_ai_2"
_TEMPLATE_MUU_BINH_THUONG_VUOT_AI_3 = "chien_tranh.thuong_vuot_ai/thuong_vuot_ai_3"
_TEMPLATE_MUU_BINH_XAC_NHAN_THUONG_VUOT_AI = "chien_tranh.muu_binh/xac_nhan_thuong_vuot_ai"
_TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_GIET_NHANH = "chien_tranh.thuong_vuot_ai/giet_nhanh"
_TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_10 = "chien_tranh.thuong_vuot_ai/cuong_cong_10"
_TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_6 = "chien_tranh.thuong_vuot_ai/cuong_cong_6"
_TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_4 = "chien_tranh.thuong_vuot_ai/cuong_cong_4"
_TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_2 = "chien_tranh.thuong_vuot_ai/cuong_cong_2"
_TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_TRUONG_THANH_10 = "chien_tranh.thuong_vuot_ai/truong_thanh_10"

# Template dùng trong quy trình Giao Tranh.
_TEMPLATE_MAIN_QUAN_SU = "main/quan_su"
_TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO = "quan_su.giao_tranh/loi_vao_giao_tranh"
_TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_SU_DUNG_CANH_BAT_TRAN = "quan_su.giao_tranh/chua_su_dung_canh_bat_tran"
_TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU = "quan_su.giao_tranh/tim_doi_thu"
_TEMPLATE_QUAN_SU_GIAO_TRANH_BAI_MIEN_CHIEN = "quan_su.giao_tranh/bai_mien_chien"
_TEMPLATE_QUAN_SU_GIAO_TRANH_CAM_NANG = "quan_su.giao_tranh/cam_nang"
_TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN = "quan_su.giao_tranh/xuat_chien"
_TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_CO_CHIEN_THUAT = "quan_su.giao_tranh/chua_co_chien_thuat"
_TEMPLATE_QUAN_SU_GIAO_TRANH_RUT_LUI = "quan_su.giao_tranh/rut_lui"
_TEMPLATE_QUAN_SU_GIAO_TRANH_THU_QUAN = "quan_su.giao_tranh/thu_quan"
_TEMPLATE_QUAN_SU_GIAO_TRANH_HOP_THOAI_THU_QUAN = "quan_su.giao_tranh/hop_thoai_thu_quan"
_TEMPLATE_QUAN_SU_GIAO_TRANH_TRAN_SAU = "quan_su.giao_tranh/tran_sau"
_TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH = "quan_su.giao_tranh/hoi_thanh"
_TEMPLATE_QUAN_SU_GIAO_TRANH_1_CO = "quan_su.giao_tranh/1_co"
_TEMPLATE_QUAN_SU_GIAO_TRANH_2_CO = "quan_su.giao_tranh/2_co"
_TEMPLATE_QUAN_SU_GIAO_TRANH_DUNG_LUONG_THAO = "quan_su.giao_tranh/dung_luong_thao"


_STEP_QUAN_DOAN_BAO_DANH = "quan_doan_bao_danh"
_STEP_QUAN_DOAN_TUI_PHUC = "quan_doan_tui_phuc"
_STEP_QUAN_DOAN_CAU_VAN = "quan_doan_cau_van"
_STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO = "quan_doan_dong_gop_luong_thao"
_STEP_QUAN_DOAN_DONG_GOP_KNB = "quan_doan_dong_gop_knb"

# Step cửa hàng
_STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH = "cua_hang_danh_vong_mua_que_lanh"

# Template dùng trong màn hình Cửa hàng.
_TEMPLATE_MAIN_CUA_HANG = "main/cua_hang"
_TEMPLATE_CUA_HANG_THUONG_THANH = "cua_hang/thuong_thanh"
_TEMPLATE_CUA_HANG_DONG_MAN_HINH = "cua_hang/dong_man_hinh_cua_hang"
_TEMPLATE_CUA_HANG_DONG_MAN_HINH_XAC_NHAN_MUA = "cua_hang/dong_man_hinh_xac_nhan_mua"
_TEMPLATE_CUA_HANG_SHOP_CHIEN_TRANH = "cua_hang/shop_chien_tranh"
_TEMPLATE_CUA_HANG_DANG_CHON_SHOP_CHIEN_TRANH = "cua_hang/dang_chon_shop_chien_tranh"
_TEMPLATE_CUA_HANG_DANH_VONG = "cua_hang.chien_tranh.danh_vong/shop_danh_vong"
_TEMPLATE_CUA_HANG_DANG_CHON_DANH_VONG = "cua_hang.chien_tranh.danh_vong/dang_chon_shop_danh_vong"
_TEMPLATE_CUA_HANG_CHUA_MUA_QUE_LANH = "cua_hang.chien_tranh.danh_vong/chua_mua_que_lanh"
_TEMPLATE_CUA_HANG_DA_MUA_QUE_LANH = "cua_hang.chien_tranh.danh_vong/da_mua_que_lanh"
_TEMPLATE_CUA_HANG_MAN_HINH_MUA_QUE_LANH = "cua_hang.chien_tranh.danh_vong.mua_que_lanh/man_hinh_mua_que_lanh"

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
_TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB = "quan_doan/quan_doan_chua_du_dieu_kien_dong_gop_knb"

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
_TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN = "hoat_dong/dang_chon_le_bao_quoc_van"
_TEMPLATE_CHUA_CHON_LE_BAO_QUOC_VAN = "hoat_dong/chua_chon_le_bao_quoc_van"
_TEMPLATE_DANG_CHON_DIEM_DANH = "hoat_dong/dang_chon_diem_danh"
_TEMPLATE_CHUA_CHON_DIEM_DANH = "hoat_dong/chua_chon_diem_danh"
_TEMPLATE_DANG_CHON_PHUC_LOI = "hoat_dong/dang_chon_phuc_loi"
_TEMPLATE_CHUA_CHON_PHUC_LOI = "hoat_dong/chua_chon_phuc_loi"
_TEMPLATE_DANG_CHON_HOAT_DONG = "hoat_dong/dang_chon_hoat_dong"
_TEMPLATE_CHUA_CHON_HOAT_DONG = "hoat_dong/chua_chon_hoat_dong"

# Template dùng bên trong tác vụ Điểm danh.
_TEMPLATE_XAC_NHAN_DIEM_DANH_BU = "hoat_dong.phuc_loi.diem_danh/xac_nhan_diem_danh_bu"
_TEMPLATE_DIEM_DANH_BU = "hoat_dong.phuc_loi.diem_danh/diem_danh_bu"
_TEMPLATE_DA_DIEM_DANH = "hoat_dong.phuc_loi.diem_danh/da_diem_danh"

# Template dùng bên trong tác vụ nhận lễ bao Quốc Vận.
_TEMPLATE_NHAN_LE_BAO_MIEN_PHI = "hoat_dong.phuc_loi.le_bao_quoc_van/chua_nhan_le_bao_mien_phi"
_TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI = "hoat_dong.phuc_loi.le_bao_quoc_van/da_nhan_le_bao_mien_phi"
_TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI1 = "hoat_dong.phuc_loi.le_bao_quoc_van/tat_thong_bao_nhan_le_bao1"
_TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI2 = "hoat_dong.phuc_loi.le_bao_quoc_van/tat_thong_bao_nhan_le_bao2"
