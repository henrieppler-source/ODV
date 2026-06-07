from __future__ import annotations

import tkinter as tk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TK_BASE_CLASS = TkinterDnD.Tk
except Exception:  # Drag & Drop bleibt optional; ohne Bibliothek läuft ODV normal weiter.
    DND_FILES = None
    TkinterDnD = None
    TK_BASE_CLASS = tk.Tk

from .app_constants import APP_NAME, APP_SHORT_NAME, APP_VERSION
from .bootstrap_mixin import BootstrapMixin
from .config_folders import ConfigFoldersMixin
from .admin_view_manager import AdminViewManagerMixin
from .admin_operations import AdminOperationsMixin
from .admin_detail_manager import AdminDetailManagerMixin
from .admin_file_ops_manager import AdminFileOpsManagerMixin
from .admin_points_detail_manager import AdminPointsDetailManagerMixin
from .admin_points_manager import AdminPointsManagerMixin
from .admin_status_manager import AdminStatusManagerMixin
from .display_manager import DisplayManagerMixin
from .admin_ui_manager import AdminUiManagerMixin
from .admin_list_manager import AdminListManagerMixin
from .file_access_manager import FileAccessManagerMixin
from .file_tree_manager import FileTreeManagerMixin
from .admin_policy_manager import AdminPolicyManagerMixin
from .path_policy_manager import PathPolicyManagerMixin
from .path_resolution_manager import PathResolutionManagerMixin
from .session_manager import SessionManagerMixin
from .help_docs import HelpDocsMixin
from .history_manager import HistoryManagerMixin
from .document_pdf_manager import DocumentPdfManagerMixin
from .pdf_management_manager import PdfManagementManagerMixin
from .mail_manager import MailManagerMixin
from .metadata_form_manager import MetadataFormManagerMixin
from .metadata_helpers import MetadataHelpersMixin
from .normalization_ui_manager import NormalizationUiManagerMixin
from .upload_manager import UploadManagerMixin
from .masterdata_manager import MasterdataManagerMixin
from .points_year_manager import PointsYearManagerMixin
from .points_special_manager import PointsSpecialManagerMixin
from .points_rules_manager import PointsRulesManagerMixin
from .postprocess_manager import PostprocessManagerMixin
from .single_instance import acquire_single_instance_lock, release_single_instance_lock
from .system_status import SystemStatusMixin
from .ui_state import UiStateMixin
from .update_manager import AppUpdateMixin
from .user_admin import UserAdminMixin
from .upload_tab import UploadTabMixin
from .file_view_manager import FileViewManagerMixin
from .preview_manager import PreviewManagerMixin
from .main_window_mixin import MainWindowMixin


class OrtschronikUploader(
    HelpDocsMixin,
    HistoryManagerMixin,
    UiStateMixin,
    SystemStatusMixin,
    AppUpdateMixin,
    AdminOperationsMixin,
    AdminDetailManagerMixin,
    AdminFileOpsManagerMixin,
    AdminStatusManagerMixin,
    AdminPointsManagerMixin,
    AdminPointsDetailManagerMixin,
    PointsYearManagerMixin,
    PointsSpecialManagerMixin,
    PointsRulesManagerMixin,
    PostprocessManagerMixin,
    MailManagerMixin,
    UserAdminMixin,
    SessionManagerMixin,
    MasterdataManagerMixin,
    ConfigFoldersMixin,
    MetadataHelpersMixin,
    NormalizationUiManagerMixin,
    UploadTabMixin,
    FileViewManagerMixin,
    FileAccessManagerMixin,
    DocumentPdfManagerMixin,
    PdfManagementManagerMixin,
    DisplayManagerMixin,
    MetadataFormManagerMixin,
    UploadManagerMixin,
    AdminUiManagerMixin,
    AdminListManagerMixin,
    FileTreeManagerMixin,
    AdminPolicyManagerMixin,
    PathPolicyManagerMixin,
    PathResolutionManagerMixin,
    AdminViewManagerMixin,
    PreviewManagerMixin,
    BootstrapMixin,
    MainWindowMixin,
    TK_BASE_CLASS,
):
    APP_NAME = APP_NAME
    APP_SHORT_NAME = APP_SHORT_NAME
    APP_VERSION = APP_VERSION
    ADMIN_WORK_FOLDER_NAMES = {"01_ABLAGE_ORTSCHRONIK", "06_ARBEIT_DER_ORTSCHRONISTEN"}
    FOLDER_GROUPS = [
        ("00_ORTSCHRONIK", "00_ORTSCHRONIK"),
        ("01_ABLAGE_ORTSCHRONIK", "01_ABLAGE_ORTSCHRONIK"),
        ("02_AUSTAUSCH", "02_AUSTAUSCH"),
        ("03_INFORMATION", "03_INFORMATION"),
        ("05_ORGA_CHRONISTEN", "05_ORGA_CHRONISTEN"),
        ("06_UNSERE_ARBEITEN", "06_UNSERE_ARBEITEN"),
        ("99_ARCHIV", "99_ARCHIV"),
        ("OWN_PLACE_FOLDER", "Eigener Ortsordner"),
        ("OTHER_PLACE_FOLDERS", "Andere Ortsordner"),
    ]

    def __init__(self):
        super().__init__()
        self.bootstrap_window()
        self.bootstrap_runtime_state()
        self.bootstrap_tk_variables()
        self.bootstrap_startup_flow()
