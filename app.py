from sys import path  # extra step because
path.append('../')  # importing GoodData SDK from root directory

from common import LoadGoodDataSdk, csv_to_sql
# from component import mycomponent # React specific component not relevant here
from helpers import csv_to_ldm_request, html_cytoscape, html_gooddata_ui_dashboard, time_it, restore_from_url, load_restore_profiles, save_restore_profiles, load_users_internal, load_users_testing, load_users_testing_template, save_users_testing, automation_rows, notification_channel_rows, pretty_json, workspace_overview_stats, dashboard_effective_filter_stats, dashboard_filter_context_records, load_plugin_list, save_plugin_list, discover_plugins_from_s3, list_workspace_plugins, register_plugin_with_workspace, write_plugin_yaml_helper
from datetime import datetime

import altair as alt
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


def get_workspace_automations(gd, workspace_id):
    """Return {schedules, alerts} for the given workspace."""
    if hasattr(gd, "get_workspace_automations"):
        return gd.get_workspace_automations(workspace_id=workspace_id)
    return gd.get_user_automations("")


def render_workspace_automation_sections(gd, workspace_id, context_label=""):
    label_suffix = f" ({context_label})" if context_label else ""
    automations = get_workspace_automations(gd, workspace_id)
    schedules = automations.get("schedules", [])
    alerts = automations.get("alerts", [])

    st.subheader(f"📅 Schedules{label_suffix}")
    if schedules:
            st.dataframe(
                pd.DataFrame(
                    automation_rows(
                        schedules,
                        table_kind="schedule",
                        include_filter_context=bool(context_label),
                    )
                ),
            width="stretch",
        )
    else:
        st.info("No schedules in this workspace.")

    st.subheader(f"🔔 Alerts{label_suffix}")
    if alerts:
            st.dataframe(
                pd.DataFrame(
                    automation_rows(
                        alerts,
                        table_kind="alert",
                        include_filter_context=bool(context_label),
                    )
                ),
            width="stretch",
        )
    else:
        st.info("No alerts in this workspace.")

    st.subheader("📬 Notification Channels")
    try:
        channels = gd.get_declarative_notification_channels()
        if channels:
            st.dataframe(pd.DataFrame(notification_channel_rows(channels)), width="stretch")
            st.caption("Organization-level notification channels (SDK: catalog_organization.get_declarative_notification_channels)")
        else:
            st.info("No notification channels in the organization.")
    except Exception as e:
        st.warning(f"Could not load notification channels: {e}")


def ensure_workspace_semantics(gd, workspace_id):
    if not workspace_id:
        st.session_state["workspace_semantics"] = {}
        return {}
    cached_workspace_id = st.session_state.get("workspace_semantics_workspace_id")
    cached_semantics = st.session_state.get("workspace_semantics")
    if cached_workspace_id == workspace_id and cached_semantics:
        return cached_semantics
    try:
        semantics = gd.collect_workspace_semantics(workspace_id)
    except Exception:
        semantics = {}
    st.session_state["workspace_semantics_workspace_id"] = workspace_id
    st.session_state["workspace_semantics"] = semantics
    return semantics


def find_dashboard_record(semantics, dashboard_title):
    for dashboard in semantics.get("dashboards", []):
        if dashboard.get("title") == dashboard_title:
            return dashboard
    return None


def find_filter_context_record(semantics, filter_context_title):
    for filter_context in semantics.get("filter_contexts", []):
        if filter_context.get("title") == filter_context_title:
            return filter_context
    return None


def find_visualization_record(semantics, visualization_title):
    for visualization in semantics.get("visualizations", []):
        if visualization.get("title") == visualization_title:
            return visualization
    return None


def rows_from_dashboard_shares(semantics, dashboard_id):
    rows = []
    for share in semantics.get("dashboard_shares", {}).get(dashboard_id, []):
        assignee_id = share.get("assignee_id")
        assignee_type = share.get("assignee_type")
        if not assignee_id or not assignee_type:
            continue
        rows.append({
            "Assignee ID": assignee_id,
            "Type": assignee_type,
            "Permissions": ", ".join(share.get("permissions", [])),
        })
    return rows


def load_default_secret_values():
    """
    Resolve optional workspace and datasource defaults from Streamlit Secrets.
    """
    return {
        "workspace_id": st.secrets.get("GOODDATA_DEFAULT_WORKSPACE", ""),
        "datasource_id": st.secrets.get("GOODDATA_DEFAULT_DATASOURCE", ""),
        "env_name": "streamlit-secrets",
    }


def main():
    # session variables
    if "gd" not in st.session_state:
        st.session_state["gd"] = LoadGoodDataSdk(st.secrets["GOODDATA_HOST"], st.secrets["GOODDATA_TOKEN"])
    if "timing" not in st.session_state:
        st.session_state["timing"] = []

    default_env_values = load_default_secret_values()
    default_workspace_id = default_env_values["workspace_id"]
    default_datasource_id = default_env_values["datasource_id"]

    # Initialize current workspace (use default or session state)
    if "current_workspace_id" not in st.session_state:
        st.session_state["current_workspace_id"] = default_workspace_id
    if "workspace_semantics" not in st.session_state:
        st.session_state["workspace_semantics"] = {}
    if "workspace_semantics_workspace_id" not in st.session_state:
        st.session_state["workspace_semantics_workspace_id"] = None
    if st.session_state["current_workspace_id"]:
        ensure_workspace_semantics(st.session_state["gd"], st.session_state["current_workspace_id"])

    st.set_page_config(
        layout="wide", page_icon="favicon.ico", page_title="Streamlit-GoodData integration demo"
    )
    org = st.session_state["gd"].organization()
    current_semantics = st.session_state.get("workspace_semantics", {})

    with st.sidebar:
        # Workspace selector (first thing)
        workspace_options = [w.name for w in st.session_state["gd"].workspaces]
        current_workspace_name = None
        if st.session_state["current_workspace_id"]:
            try:
                current_ws = st.session_state["gd"].specific(
                    st.session_state["current_workspace_id"], of_type="workspace", by="id"
                )
                current_workspace_name = current_ws.name
            except Exception:
                current_workspace_name = None

        selected_workspace_name = st.selectbox(
            "Select Workspace",
            options=workspace_options,
            index=workspace_options.index(current_workspace_name) if current_workspace_name and current_workspace_name in workspace_options else 0,
            key="workspace_selector"
        )

        # Get workspace ID from name
        selected_workspace_id = st.session_state["gd"].get_id(selected_workspace_name, of_type="workspace")

        # Check if workspace changed and confirm immediately (no separate confirm button needed)
        workspace_changed = selected_workspace_id != st.session_state.get("current_workspace_id")
        if workspace_changed:
            st.warning(f"⚠️ Switching to **{selected_workspace_name}** — confirm to load.")
            if st.button("✅ Confirm Switch", type="primary", key="confirm_switch_btn"):
                st.session_state["current_workspace_id"] = selected_workspace_id
                try:
                    st.session_state["workspace_semantics"] = st.session_state["gd"].collect_workspace_semantics(selected_workspace_id)
                    st.session_state["workspace_semantics_workspace_id"] = selected_workspace_id
                    st.success(f"✅ Switched to: {selected_workspace_name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to load workspace: {str(e)}")

        with st.expander("Workspace Content"):
            # Content View: single label + radio (no duplicated "Content View" header)
            dashboard_view_mode = st.radio(
                "Content View",
                ["Overview", "Dependent Entities Graph", "Dashboard Schema", "Dashboard Embed", "Schedules", "Dashboard Shares", "Filter Contexts"],
                horizontal=True,
                index=0,
                key="dashboard_view_mode_radio"
            )
            st.session_state["dashboard_view_mode"] = dashboard_view_mode

            if current_semantics:
                dashboard_titles = [d.get("title") for d in current_semantics.get("dashboards", []) if d.get("title")]
                has_dashboards = len(dashboard_titles) > 0
                ws_dash_list = st.selectbox(
                    "Select a dashboard",
                    dashboard_titles if has_dashboards else ["(no dashboards)"],
                    disabled=not has_dashboards,
                    key="ws_dash_list_selector"
                )
                st.session_state["ws_dash_list"] = ws_dash_list
                selected_dashboard_record = find_dashboard_record(current_semantics, ws_dash_list)
                st.session_state["selected_dashboard_id"] = selected_dashboard_record.get("id") if selected_dashboard_record else None

            else:
                has_dashboards = False
                ws_dash_list = "(no dashboards)"
                st.session_state["ws_dash_list"] = ws_dash_list

            st.divider()

            # Data Actions section
            st.subheader("Data Actions")
            if current_semantics:
                insight_titles = [d.get("title") for d in current_semantics.get("visualizations", []) if d.get("title")]
                has_insights = len(insight_titles) > 0
                df_insight = st.selectbox(
                    "Select an Insight",
                    insight_titles if has_insights else ["(no insights)"],
                    disabled=not has_insights,
                    key="df_insight_selector"
                )
                st.session_state["df_insight"] = df_insight

                # Show default datasource info
                if default_datasource_id:
                    st.caption(f"Using default datasource: {default_datasource_id}")

                col1, col2 = st.columns(2)
                with col1:
                    clear_cache = st.button("Clear Cache", disabled=not default_datasource_id, key="clear_cache_btn")
                with col2:
                    display_insight = st.button("Test Retrieval", disabled=not has_insights, key="display_insight_btn")
            else:
                has_insights = False
                df_insight = "(no insights)"
                clear_cache = False
                display_insight = False

            st.divider()

            # Data preparation section
            st.subheader("Data Preparation")
            prep_option = st.radio(
                "Choose data preparation method:",
                ("CSV as SQL dataset", "CSV S3 uploader", "LDM preparation"),
                horizontal=True,
                key="prep_option_radio"
            )
            st.session_state["prep_option"] = prep_option
            uploaded_file = st.file_uploader("Upload CSV file", type=["csv"], key="csv_uploader")
            st.session_state["uploaded_file"] = uploaded_file
            upload_csv = st.button("Process CSV", disabled=uploaded_file is None, key="upload_csv_btn")


        with st.expander("Admin Access"):
            st.write("**Organization Details**")
            st.write("Hostname:", org.attributes.hostname)
            st.write("Organization id:", org.id)
            st.write("Identity provider:", org.attributes.oauth_issuer_location)

            st.divider()
            admin_mode = st.radio(
                "Mode",
                ["none", "internal users", "test users", "backup and restore", "dashboard plugins"],
                index=0,
                key="admin_mode_radio",
            )
            st.session_state["restore_users_internal"] = (admin_mode == "internal users")
            st.session_state["restore_users_testing"] = (admin_mode == "test users")
            st.session_state["restore_mode"] = (admin_mode == "backup and restore")

            if admin_mode == "backup and restore":
                st.button("Backup selected workspace", key="backup_btn")

    # Get active workspace
    current_ws_id = st.session_state.get("current_workspace_id", default_workspace_id)
    if current_ws_id:
        try:
            active_ws = st.session_state["gd"].specific(current_ws_id, of_type="workspace", by="id")
        except Exception:
            active_ws = None
    else:
        active_ws = None
    current_semantics = ensure_workspace_semantics(st.session_state["gd"], current_ws_id) if current_ws_id else {}

    # Handle restore button click FIRST (before showing restore mode UI)
    if st.session_state.get("restore_button_clicked", False):
        # Reset the flag immediately to prevent re-execution
        st.session_state["restore_button_clicked"] = False

        ldm_url = st.session_state.get("ldm_url", "")
        workspace_analytics_url = st.session_state.get("workspace_analytics_url", "")
        restore_workspace_id = st.session_state.get("restore_workspace_id", "")
        restore_datasource_id = st.session_state.get("restore_datasource_id", "")
        workspace_data_filters_url = st.session_state.get("workspace_data_filters_url", "")

        if not ldm_url:
            st.warning("⚠️ Please enter an LDM JSON URL")
        elif not workspace_analytics_url:
            st.warning("⚠️ Please enter a workspace analytics JSON URL")
        else:
            try:
                with st.spinner("🔄 Restoring workspace..."):
                    result = restore_from_url(
                        gd_sdk=st.session_state["gd"],
                        host=st.secrets["GOODDATA_HOST"],
                        token=st.secrets["GOODDATA_TOKEN"],
                        workspace_id=restore_workspace_id if restore_workspace_id else None,
                        datasource_id=restore_datasource_id if restore_datasource_id else None,
                        ldm_url=ldm_url,
                        workspace_analytics_url=workspace_analytics_url,
                        workspace_data_filters_url=workspace_data_filters_url if workspace_data_filters_url else None
                    )
            except Exception as e:
                st.error(f"❌ **Error during restore execution:** {str(e)}")
                import traceback
                st.error(f"**Traceback:**\n```\n{traceback.format_exc()}\n```")
                result = {
                    "success": False,
                    "errors": [f"Exception during restore: {str(e)}"],
                    "warnings": [],
                    "steps": [],
                    "statistics": {
                        "workspace_created": False,
                        "workspace_updated": False,
                        "wdf_created": 0,
                        "wdf_updated": 0,
                        "ldm_updated": False,
                        "analytics_updated": False
                    },
                    "report": [f"❌ Exception occurred: {str(e)}"]
                }

            # Display report
            st.markdown("---")
            st.subheader("📋 Restore Report")

            # Status badge
            if result["success"]:
                st.success("✅ **Restore completed successfully!**")
            else:
                st.error("❌ **Restore completed with errors**")

            # Statistics
            stats = result["statistics"]
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Workspace", "✓" if (stats["workspace_created"] or stats["workspace_updated"]) else "—")
            with col2:
                st.metric("WDF", f"{stats['wdf_created'] + stats['wdf_updated']}" if (stats["wdf_created"] + stats["wdf_updated"] > 0) else "—")
            with col3:
                st.metric("LDM", "✓" if stats["ldm_updated"] else "—")
            with col4:
                st.metric("Analytics", "✓" if stats["analytics_updated"] else "—")

            # Detailed report
            with st.expander("📄 Detailed Report", expanded=True):
                for line in result["report"]:
                    if line.startswith("**"):
                        st.markdown(line)
                    elif line.startswith("✅"):
                        st.success(line)
                    elif line.startswith("❌"):
                        st.error(line)
                    elif line.startswith("⚠️"):
                        st.warning(line)
                    elif line.startswith("📥") or line.startswith("📦") or line.startswith("🏢") or line.startswith("📊"):
                        st.markdown(f"**{line}**")
                    else:
                        st.text(line)

            # Errors section
            if result["errors"]:
                with st.expander("❌ Errors", expanded=True):
                    for error in result["errors"]:
                        st.error(f"• {error}")

            # Warnings section
            if result["warnings"]:
                with st.expander("⚠️ Warnings", expanded=False):
                    for warning in result["warnings"]:
                        st.warning(f"• {warning}")

            # Steps completed
            if result["steps"]:
                with st.expander("✅ Steps Completed", expanded=False):
                    for step in result["steps"]:
                        st.success(f"• {step}")

    # Show restore profiles table in main area if restore mode is enabled
    elif st.session_state.get("restore_mode", False):
        st.header("📋 Restore Profiles Management")

        # Load profiles
        if "restore_profiles" not in st.session_state:
            st.session_state["restore_profiles"] = load_restore_profiles()

        profiles_data = st.session_state["restore_profiles"]
        profiles_list = profiles_data.get("profiles", [])

        # Ensure all profiles have required structure
        column_order = ["name", "workspace_id", "datasource_id", "ldm_url", "workspace_analytics_url", "workspace_data_filters_url"]
        normalized_profiles = []
        for profile in profiles_list:
            normalized_profile = {}
            # Add columns in order
            for col in column_order:
                normalized_profile[col] = profile.get(col, "")
            # Add any other fields
            for k, v in profile.items():
                if k not in normalized_profile:
                    normalized_profile[k] = v
            normalized_profiles.append(normalized_profile)

        # If empty, add one empty row
        if not normalized_profiles:
            normalized_profiles = [dict.fromkeys(column_order, "")]

        # Editable table in main area
        st.write("**Restore Profiles Table** (Edit directly in the table, then select a row to deploy)")
        edited_profiles = st.data_editor(
            normalized_profiles,
            width="stretch",
            num_rows="dynamic",
            column_config={
                "name": st.column_config.TextColumn("Profile Name", required=True),
                "workspace_id": st.column_config.TextColumn("Workspace ID"),
                "datasource_id": st.column_config.TextColumn("Data Source ID"),
                "ldm_url": st.column_config.TextColumn("LDM URL", width="large"),
                "workspace_analytics_url": st.column_config.TextColumn("Analytics URL", width="large"),
                "workspace_data_filters_url": st.column_config.TextColumn("WDF URL", width="large")
            },
            key="restore_profiles_table"
        )

        # Save profiles button
        col1, col2 = st.columns([1, 4])
        with col1:
            save_profiles = st.button("💾 Save Profiles", type="primary")
        with col2:
            if save_profiles:
                # Clean up profiles: add IDs and remove empty values
                new_profiles = []
                for i, profile in enumerate(edited_profiles):
                    # Add ID if missing
                    if "id" not in profile or not profile.get("id"):
                        profile_name = profile.get("name", "").strip()
                        if profile_name:
                            profile["id"] = profile_name.lower().replace(" ", "_").replace("-", "_")
                        else:
                            profile["id"] = f"profile_{i}"

                    # Remove empty string values (but keep the structure)
                    cleaned_profile = {}
                    for k, v in profile.items():
                        if v is not None and v != "":
                            cleaned_profile[k] = v

                    # Only add if it has at least a name
                    if cleaned_profile.get("name"):
                        new_profiles.append(cleaned_profile)

                profiles_data["profiles"] = new_profiles
                if save_restore_profiles(profiles_data):
                    st.session_state["restore_profiles"] = profiles_data
                    st.success("✅ Profiles saved successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to save profiles")

        st.divider()
        st.subheader("🚀 Deploy Configuration")

        # Profile selection
        if "selected_profile_idx" not in st.session_state:
            st.session_state["selected_profile_idx"] = 0

        if len(edited_profiles) > 0:
            # Get profile names for dropdown
            profile_names = ["-- Select Profile --"]
            for profile in edited_profiles:
                name = profile.get("name", "").strip()
                profile_names.append(name if name else "Unnamed")

            selected_profile_idx = st.selectbox(
                "Select Profile to Deploy",
                range(len(profile_names)),
                index=st.session_state.get("selected_profile_idx", 0),
                format_func=lambda x: profile_names[x] if x < len(profile_names) else "-- Select Profile --",
                key="profile_selector"
            )
            st.session_state["selected_profile_idx"] = selected_profile_idx

            # Load selected profile values
            if selected_profile_idx > 0 and selected_profile_idx <= len(edited_profiles):
                selected_profile = edited_profiles[selected_profile_idx - 1]
                selected_workspace_id = str(selected_profile.get("workspace_id", "")).strip()
                selected_datasource_id = str(selected_profile.get("datasource_id", "")).strip()
                selected_ldm_url = str(selected_profile.get("ldm_url", "")).strip()
                selected_analytics_url = str(selected_profile.get("workspace_analytics_url", "")).strip()
                selected_wdf_url = str(selected_profile.get("workspace_data_filters_url", "")).strip()
            else:
                selected_workspace_id = ""
                selected_datasource_id = ""
                selected_ldm_url = ""
                selected_analytics_url = ""
                selected_wdf_url = ""
        else:
            selected_profile_idx = 0
            st.session_state["selected_profile_idx"] = 0
            selected_workspace_id = ""
            selected_datasource_id = ""
            selected_ldm_url = ""
            selected_analytics_url = ""
            selected_wdf_url = ""

        # Form fields (pre-filled from selected profile or env defaults)
        col1, col2 = st.columns(2)
        with col1:
            restore_workspace_id = st.text_input(
                "Workspace ID (optional)",
                value=selected_workspace_id if selected_workspace_id else default_workspace_id,
                placeholder=default_workspace_id if default_workspace_id else "Enter workspace ID",
                help="Target workspace ID. If not provided, will use GOODDATA_DEFAULT_WORKSPACE from environment."
            )
        with col2:
            restore_datasource_id = st.text_input(
                "Data Source ID (optional)",
                value=selected_datasource_id if selected_datasource_id else default_datasource_id,
                placeholder=default_datasource_id if default_datasource_id else "Enter data source ID",
                help="Data source ID to update references in LDM. If not provided, will use GOODDATA_DEFAULT_DATASOURCE from environment."
            )

        default_ldm_url = "https://raw.githubusercontent.com/gooddata/gooddata-public-demos/refs/heads/master/ecommerce-demo/workspaces/demo/ldm.json"
        default_analytics_url = "https://raw.githubusercontent.com/gooddata/gooddata-public-demos/refs/heads/master/ecommerce-demo/workspaces/demo/workspaceAnalytics.json"
        default_wdf_url = "https://raw.githubusercontent.com/gooddata/gooddata-public-demos/refs/heads/master/ecommerce-demo/workspaces/demo/workspaceDataFilters.json"

        ldm_url = st.text_input(
            "LDM JSON URL *",
            value=selected_ldm_url if selected_ldm_url else default_ldm_url,
            help="Direct URL to the logical data model JSON file"
        )

        workspace_data_filters_url = st.text_input(
            "Workspace Data Filters JSON URL (optional)",
            value=selected_wdf_url if selected_wdf_url else default_wdf_url,
            help="Direct URL to the workspace data filters JSON file. Required if LDM references workspace data filters."
        )

        workspace_analytics_url = st.text_input(
            "Workspace Analytics JSON URL *",
            value=selected_analytics_url if selected_analytics_url else default_analytics_url,
            help="Direct URL to the workspace analytics JSON file"
        )

        # Store values in session state for access outside the if block
        st.session_state["restore_workspace_id"] = restore_workspace_id
        st.session_state["restore_datasource_id"] = restore_datasource_id
        st.session_state["ldm_url"] = ldm_url
        st.session_state["workspace_analytics_url"] = workspace_analytics_url
        st.session_state["workspace_data_filters_url"] = workspace_data_filters_url

        restore_button = st.button(
            "🚀 Deploy",
            disabled=not (ldm_url and workspace_analytics_url),
            type="primary",
            width="stretch",
            key="restore_deploy_button"
        )

        # Set restore button clicked state when button is clicked
        if restore_button:
            st.session_state["restore_button_clicked"] = True
            st.rerun()

    # Handle user restoration - Internal users
    elif st.session_state.get("restore_users_internal", False):
        st.header("👥 Restore Users Internal")

        # Load internal users
        users_data = load_users_internal()
        users_list = users_data.get("users", [])

        if not users_list:
            st.warning("⚠️ No users found in restore_SEE_users.json")
        else:
            # Get current deployment users
            try:
                current_users = st.session_state["gd"].users
                current_user_ids = {u.id for u in current_users}
                # Get admin users (users in admin groups)
                admin_user_ids = set()
                for user in current_users:
                    if hasattr(user, 'user_groups') and user.user_groups:
                        for group in user.user_groups:
                            # Safely check group name
                            group_name = getattr(group, 'name', None) or getattr(group, 'user_group_name', None) or ""
                            if group_name and "admin" in str(group_name).lower():
                                admin_user_ids.add(user.id)
            except Exception as e:
                st.error(f"❌ Failed to load current users: {str(e)}")
                import traceback
                st.error(f"Traceback: {traceback.format_exc()}")
                current_user_ids = set()
                admin_user_ids = set()

            # Show ALL users from JSON, mark missing ones
            all_users_table = []
            non_admin_existing = []
            admin_existing = []
            missing = []

            for user in users_list:
                user_id = user.get("id", "")
                user_name = f"{user.get('firstname', '')} {user.get('lastname', '')}".strip() or user_id
                user_email = user.get("email", "")

                # Get user groups from JSON
                json_user_groups = []
                json_groups = user.get("userGroups", [])
                for group_ref in json_groups:
                    if isinstance(group_ref, dict):
                        group_id = group_ref.get("id", "")
                        # Try to find group name from userGroups list in JSON
                        for ug in users_data.get("userGroups", []):
                            if ug.get("id") == group_id:
                                json_user_groups.append(ug.get("name", group_id))
                                break
                        if not any(ug.get("id") == group_id for ug in users_data.get("userGroups", [])):
                            json_user_groups.append(group_id)
                    else:
                        json_user_groups.append(str(group_ref))

                # Check if user exists in deployment
                exists_in_deployment = user_id in current_user_ids
                is_admin = user_id in admin_user_ids

                # Get current user groups from deployment
                current_user_groups = []
                if exists_in_deployment:
                    try:
                        current_user = st.session_state["gd"].specific(user_id, of_type="user", by="id")
                        if hasattr(current_user, 'user_groups') and current_user.user_groups:
                            for g in current_user.user_groups:
                                group_name = getattr(g, 'name', None) or getattr(g, 'user_group_name', None) or getattr(g, 'id', None) or str(g)
                                if group_name:
                                    current_user_groups.append(str(group_name))
                    except Exception:
                        pass

                # Determine status
                if not exists_in_deployment:
                    status = "Missing"
                    missing.append(user)
                elif is_admin:
                    status = "Admin"
                    admin_existing.append(user)
                else:
                    status = "Active"
                    non_admin_existing.append(user)

                # Format user ID with strikethrough if missing
                display_user_id = f"~~{user_id}~~" if not exists_in_deployment else user_id
                display_name = f"~~{user_name}~~" if not exists_in_deployment else user_name
                display_email = f"~~{user_email}~~" if not exists_in_deployment else user_email

                all_users_table.append({
                    "Select": False if not exists_in_deployment else False,  # Can't select missing users
                    "User ID": display_user_id,
                    "Name": display_name,
                    "Email": display_email,
                    "Status": status,
                    "JSON Groups": ", ".join(json_user_groups) if json_user_groups else "—",
                    "Current Groups": ", ".join(current_user_groups) if current_user_groups else "—",
                    "Workspace": ""
                })

            # Show summary
            st.write(f"**Users Summary:**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total in JSON", len(users_list))
            with col2:
                st.metric("Active (Non-Admin)", len(non_admin_existing))
            with col3:
                st.metric("Admin", len(admin_existing))
            with col4:
                st.metric("Missing", len(missing))

            if missing:
                st.info(f"ℹ️ {len(missing)} user(s) from JSON not found in current deployment (shown with strikethrough)")

            if all_users_table:
                st.write(f"**All Users from JSON** (Missing users shown with strikethrough)")

                # Prepare table data
                table_data = all_users_table

                # Editable table
                st.write("**Users Table** (Select users and assign workspaces - Missing users cannot be selected)")
                edited_table = st.data_editor(
                    table_data,
                    width="stretch",
                    column_config={
                        "Select": st.column_config.CheckboxColumn("Select", default=False),
                        "User ID": st.column_config.TextColumn("User ID", disabled=True),
                        "Name": st.column_config.TextColumn("Name", disabled=True),
                        "Email": st.column_config.TextColumn("Email", disabled=True),
                        "Status": st.column_config.TextColumn("Status", disabled=True),
                        "JSON Groups": st.column_config.TextColumn("JSON Groups", disabled=True),
                        "Current Groups": st.column_config.TextColumn("Current Groups", disabled=True),
                        "Workspace": st.column_config.SelectboxColumn(
                            "Workspace",
                            options=[""] + [w.name for w in st.session_state["gd"].workspaces],
                            required=False
                        )
                    },
                    key="users_internal_table"
                )

                # Get selected users and their workspace assignments
                selected_user_workspaces = {}
                for row in edited_table:
                    if row.get("Select", False):
                        user_id_raw = row.get("User ID", "")
                        # Remove strikethrough formatting if present
                        user_id = user_id_raw.replace("~~", "").strip()
                        workspace_name = row.get("Workspace", "").strip()
                        status = row.get("Status", "")

                        # Only allow selection of existing users (not missing ones)
                        if user_id and workspace_name and status != "Missing":
                            selected_user_workspaces[user_id] = workspace_name

                st.session_state["selected_user_workspaces"] = selected_user_workspaces

                if selected_user_workspaces:
                    st.write(f"**Ready to assign {len(selected_user_workspaces)} user(s) to workspaces:**")
                    for user_id, workspace_name in selected_user_workspaces.items():
                        st.write(f"- {user_id} → {workspace_name}")

                    deploy_users_btn = st.button(
                        f"🚀 Assign {len(selected_user_workspaces)} User(s) to Workspaces",
                        type="primary",
                        key="deploy_users_internal_btn"
                    )

                    if deploy_users_btn:
                        st.session_state["deploy_users_internal_clicked"] = True
            else:
                st.info("ℹ️ No non-admin users found in current deployment. All users from JSON are either admins or not present.")

    # Handle user restoration - Testing users
    elif st.session_state.get("restore_users_testing", False):
        st.header("🧪 Restore Users Testing")

        # Load testing users
        if "users_testing" not in st.session_state:
            st.session_state["users_testing"] = load_users_testing()

        # Option to reset from template
        col1, col2 = st.columns([1, 4])
        with col1:
            reset_from_template = st.button("🔄 Reset from Template", help="Reset to template configuration", key="reset_testing_template_btn")
        with col2:
            st.caption("💡 Edit the template in `restore_test_users_template.json` to change the default structure")

        if reset_from_template:
            st.session_state["users_testing"] = load_users_testing_template()
            st.success("✅ Reset to template configuration")
            st.rerun()

        users_data = st.session_state["users_testing"]
        users_list = users_data.get("users", [])
        user_groups_list = users_data.get("userGroups", [])

        # Editable table for users
        st.write("**Testing Users Configuration** (Edit directly in the table)")

        # Normalize users for editing
        column_order = ["id", "firstname", "lastname", "email", "userGroups"]
        normalized_users = []
        for user in users_list:
            normalized_user = {}
            for col in column_order:
                if col == "userGroups":
                    # Convert userGroups list to string representation
                    groups = user.get(col, [])
                    if isinstance(groups, list):
                        normalized_user[col] = ", ".join([g.get("id", "") if isinstance(g, dict) else str(g) for g in groups])
                    else:
                        normalized_user[col] = str(groups)
                else:
                    normalized_user[col] = user.get(col, "")
            normalized_users.append(normalized_user)

        if not normalized_users:
            normalized_users = [dict.fromkeys(column_order, "")]

        edited_users = st.data_editor(
            normalized_users,
            width="stretch",
            num_rows="dynamic",
            column_config={
                "id": st.column_config.TextColumn("User ID", required=True),
                "firstname": st.column_config.TextColumn("First Name"),
                "lastname": st.column_config.TextColumn("Last Name"),
                "email": st.column_config.TextColumn("Email"),
                "userGroups": st.column_config.TextColumn("User Groups (comma-separated IDs)")
            },
            key="users_testing_table"
        )

        # Save button
        col1, col2 = st.columns([1, 4])
        with col1:
            save_users_testing = st.button("💾 Save Configuration", type="primary")

        if save_users_testing:
            # Convert back to proper format
            new_users = []
            for user_row in edited_users:
                if user_row.get("id"):
                    user_obj = {
                        "id": user_row.get("id", ""),
                        "firstname": user_row.get("firstname", ""),
                        "lastname": user_row.get("lastname", ""),
                        "email": user_row.get("email", ""),
                        "permissions": [],
                        "settings": [],
                        "userGroups": []
                    }
                    # Parse userGroups string
                    groups_str = user_row.get("userGroups", "")
                    if groups_str:
                        group_ids = [g.strip() for g in groups_str.split(",") if g.strip()]
                        user_obj["userGroups"] = [{"id": gid, "type": "userGroup"} for gid in group_ids]
                    new_users.append(user_obj)

            users_data["users"] = new_users
            if save_users_testing(users_data):
                st.success("✅ Configuration saved!")
                st.session_state["users_testing"] = users_data
            else:
                st.error("❌ Failed to save configuration")

        st.divider()
        st.write("**Deploy Testing Users**")

        # Workspace selector for deployment
        workspace_options = [w.name for w in st.session_state["gd"].workspaces]
        selected_workspace_name_testing = st.selectbox(
            "Select Workspace to Deploy Users",
            options=["-- Select Workspace --"] + workspace_options,
            key="user_workspace_selector_testing"
        )

        if selected_workspace_name_testing and selected_workspace_name_testing != "-- Select Workspace --":
            selected_workspace_id_testing = st.session_state["gd"].get_id(selected_workspace_name_testing, of_type="workspace")

            deploy_testing_users_btn = st.button(
                "🚀 Deploy Testing Users",
                disabled=not users_list,
                type="primary",
                key="deploy_users_testing_btn"
            )

            if deploy_testing_users_btn:
                st.session_state["deploy_users_testing_clicked"] = True
                st.session_state["deploy_users_testing_workspace_id"] = selected_workspace_id_testing

    # Dashboard plugins registry
    elif st.session_state.get("admin_mode_radio") == "dashboard plugins":
        st.header("Dashboard Plugins Registry")

        plugin_data = load_plugin_list()
        plugins = plugin_data.get("plugins", [])

        if not plugins:
            st.warning("No plugins found in DB_Plugin_list.json")
        else:
            # Summary counts
            deployed = [p for p in plugins if p.get("url")]
            local_only = [p for p in plugins if not p.get("url")]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Plugins", len(plugins))
            with col2:
                st.metric("Deployed to S3", len(deployed))
            with col3:
                st.metric("Local Source Only", len(local_only))

            st.divider()

            # Build display table
            table_rows = []
            for p in plugins:
                trigger = p.get("trigger", {})
                trigger_type = trigger.get("type", "none")
                if trigger_type == "visual_name":
                    trigger_label = "visual: " + ", ".join(trigger.get("visual_names", []))
                elif trigger_type == "visual_type":
                    trigger_label = "type: " + ", ".join(trigger.get("visual_types", []))
                else:
                    trigger_label = "none"

                table_rows.append({
                    "Name": p.get("name", p["id"]),
                    "Bucket": p.get("bucket", "—"),
                    "Trigger": trigger_label,
                    "Source Project": p.get("source_project", "—"),
                    "Compiled": "yes" if p.get("react_compiled") else "no",
                    "URL": p.get("url", ""),
                    "Description": p.get("description", ""),
                })

            edited = st.data_editor(
                table_rows,
                width="stretch",
                num_rows="fixed",
                column_config={
                    "Name": st.column_config.TextColumn("Name", disabled=True),
                    "Bucket": st.column_config.TextColumn("Bucket", disabled=True),
                    "Trigger": st.column_config.TextColumn("Trigger", width="medium"),
                    "Source Project": st.column_config.TextColumn("Source Project", width="medium"),
                    "Compiled": st.column_config.TextColumn("Compiled", disabled=True),
                    "URL": st.column_config.LinkColumn("URL", width="large"),
                    "Description": st.column_config.TextColumn("Description", width="large"),
                },
                key="plugins_table",
            )

            st.divider()
            col1, col2, col3 = st.columns([1, 1, 5])
            with col1:
                if st.button("💾 Save Changes", type="primary", key="save_plugins_btn"):
                    for i, row in enumerate(edited):
                        if i < len(plugins):
                            plugins[i]["description"] = row.get("Description", "")
                    plugin_data["plugins"] = plugins
                    if save_plugin_list(plugin_data):
                        st.success("Saved.")
                    else:
                        st.error("Failed to save.")
            with col2:
                if st.button("🔄 Discover from S3", key="discover_plugins_s3_btn"):
                    with st.spinner("Scanning S3 buckets…"):
                        try:
                            env_vars = dict(st.secrets)
                            result = discover_plugins_from_s3(env_vars)
                            added = result.get("added", [])
                            upd = result.get("updated", [])
                            errs = result.get("errors", [])
                            st.success(
                                f"Discovery done — {len(added)} added, {len(upd)} updated, "
                                f"{result.get('total', 0)} total"
                            )
                            if added:
                                st.info("Added: " + ", ".join(added))
                            if errs:
                                for e in errs:
                                    st.warning(e)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Sync failed: {e}")

            with st.expander("Raw JSON"):
                st.code(pretty_json(plugin_data), language="json")

            st.divider()
            st.subheader("Deploy to Workspace")

            # Show what's already registered in the current workspace
            current_ws_id_for_plugins = st.session_state.get("current_workspace_id", "")
            if current_ws_id_for_plugins:
                try:
                    registered = list_workspace_plugins(
                        st.secrets["GOODDATA_HOST"], st.secrets["GOODDATA_TOKEN"], current_ws_id_for_plugins
                    )
                except Exception:
                    registered = []

                registered_ids = {p.get("id") for p in registered}
                if registered:
                    st.caption(f"Already registered in this workspace ({len(registered)}):")
                    reg_rows = [
                        {
                            "ID": p.get("id", ""),
                            "Name": (p.get("attributes") or {}).get("name", ""),
                            "URL": (p.get("attributes") or {}).get("url", ""),
                        }
                        for p in registered
                    ]
                    st.dataframe(reg_rows, width="stretch", hide_index=True)
                else:
                    st.caption("No plugins registered in this workspace yet.")

                st.divider()

                # Selector: only plugins with a deployed URL
                deployable = [p for p in plugins if p.get("url")]
                deployable_names = [f"{p['name']}  [{p['id']}]" for p in deployable]

                selected_deploy_name = st.selectbox(
                    "Select plugin to register",
                    options=deployable_names,
                    key="deploy_plugin_selector",
                )
                selected_deploy_plugin = deployable[deployable_names.index(selected_deploy_name)] if deployable_names else None

                if selected_deploy_plugin:
                    already = selected_deploy_plugin["id"] in registered_ids
                    st.caption(
                        f"URL: {selected_deploy_plugin['url']}"
                        + ("  ✅ already registered" if already else "")
                    )

                    col1, col2 = st.columns(2)
                    with col1:
                        label = "🔄 Update in workspace" if already else "🚀 Register in workspace"
                        if st.button(label, type="primary", key="register_plugin_btn"):
                            with st.spinner("Calling GoodData API…"):
                                result = register_plugin_with_workspace(
                                    st.secrets["GOODDATA_HOST"],
                                    st.secrets["GOODDATA_TOKEN"],
                                    current_ws_id_for_plugins,
                                    selected_deploy_plugin,
                                )
                            if result["success"]:
                                st.success(f"✅ Plugin {result['action']}: `{result['id']}`")
                                st.rerun()
                            else:
                                st.error(f"❌ {result['error']}")
                    with col2:
                        if st.button("📄 Write YAML to analytics/", key="write_yaml_btn"):
                            try:
                                path = write_plugin_yaml_helper(selected_deploy_plugin)
                                st.success(f"Written: `{path}`")
                            except Exception as e:
                                st.error(f"❌ {e}")
            else:
                st.info("Select a workspace first to deploy plugins.")

    # Handle data actions (button clicks - check these before view modes)
    elif st.session_state.get("clear_cache_btn", False):
        if default_datasource_id:
            st.session_state["gd"].clear_cache(ds_id=default_datasource_id)
            st.success(f"✅ Cache cleared for datasource: {default_datasource_id}")
            st.rerun()  # Rerun to reset button state
        else:
            st.error("❌ No default datasource ID found. Please set GOODDATA_DEFAULT_DATASOURCE in your environment.")
            st.rerun()  # Rerun to reset button state
    elif st.session_state.get("display_insight_btn", False):
        df_insight = st.session_state.get("df_insight", "")
        if df_insight and df_insight != "(no insights)":
            if not current_semantics:
                st.error("❌ No analytics content available. Please ensure a workspace with content is selected.")
            else:
                st.info(f"Testing retrieval of insight '{df_insight}' from default datasource '{default_datasource_id}'...")
                t0 = time_it()
                insight_obj = find_visualization_record(current_semantics, df_insight)
                if insight_obj is not None:
                    try:
                        # Get insight ID first
                        insight_id = insight_obj.get("id")
                        # Use GoodData pandas to get the data frame
                        frames = st.session_state["gd"]._gp.data_frames(current_ws_id)
                        active_ins = frames.for_visualization(visualization_id=insight_id)
                        t1 = time_it(t0, True)
                        st.success(f"Insight retrieved in {t1:.2f} seconds.")
                        # Append timing info
                        st.session_state["timing"].append({
                            "insight": df_insight,
                            "datasource": default_datasource_id,
                            "timestamp": datetime.now().isoformat(),
                            "elapsed": t1
                        })
                        # Show time series plot for ALL insights
                        if st.session_state["timing"]:

                            timing_data = st.session_state["timing"]
                            timing_data = sorted(timing_data, key=lambda x: (x["insight"], x["timestamp"]))

                            # Convert to DataFrame for Altair
                            df_timing = pd.DataFrame(timing_data)
                            # Ensure timestamp is datetime
                            df_timing['timestamp'] = pd.to_datetime(df_timing['timestamp'])

                            st.caption("Time series of retrieval times for all insights.")
                            chart = alt.Chart(df_timing).mark_line(point=True).encode(
                                x=alt.X('timestamp:T', title='Timestamp'),
                                y=alt.Y('elapsed:Q', title='Retrieval time (s)'),
                                color=alt.Color('insight:N', title='Insight'),
                                tooltip=['insight', 'datasource', 'timestamp:T', 'elapsed:Q']
                            ).properties(width='container', height=350)
                            st.altair_chart(chart, width="stretch")

                            display_data = [
                                {
                                    "Insight": item["insight"],
                                    "Data source": item["datasource"],
                                    "Timestamp": item["timestamp"],
                                    "Retrieval time (s)": item["elapsed"]
                                }
                                for item in timing_data
                            ]
                            st.dataframe(display_data, width="stretch")
                        # Show the dataframe with the insight's content
                        st.caption("Insight object data frame (actual data):")
                        st.dataframe(active_ins)
                    except Exception as e:
                        st.error(f"Error retrieving insight: {e}")
                else:
                    st.warning("Selected insight not found.")
        else:
            st.warning("Please select an insight first.")

    # Handle dashboard view modes (only if no button actions and not in restore mode)
    elif not st.session_state.get("restore_mode", False):
        dashboard_view_mode = st.session_state.get("dashboard_view_mode", "Overview")

        if dashboard_view_mode == "Filter Contexts":
            if current_semantics:
                selected_dashboard_id = st.session_state.get("selected_dashboard_id")
                filter_context_records = dashboard_filter_context_records(
                    current_semantics,
                    selected_dashboard_id,
                )

                if filter_context_records:
                    st.write(f"**Filter Contexts** - {active_ws.name if active_ws else 'Current Workspace'}")
                    for index, selected_fc in enumerate(filter_context_records, start=1):
                        title = selected_fc.get("title") or selected_fc.get("id") or f"Filter Context {index}"
                        fc_data = [{
                            "ID": selected_fc.get("id", "N/A"),
                            "Title": title,
                            "Description": selected_fc.get("description", "") or "",
                            "Type": "Filter Context"
                        }]
                        st.dataframe(pd.DataFrame(fc_data), width="stretch", hide_index=True)
                        fc_dict = selected_fc.get("raw", {})
                        content = fc_dict.get("content") or {}
                        filters_list = selected_fc.get("filters", [])
                        if filters_list:
                            for i, f in enumerate(filters_list):
                                if isinstance(f, dict):
                                    if "dateFilter" in f:
                                        df = f["dateFilter"]
                                        st.markdown(f"**Filter {i+1}: Date** — granularity: `{df.get('granularity', '')}`, from: `{df.get('from')}`, to: `{df.get('to')}`, type: `{df.get('type', '')}`")
                                    elif "attributeFilter" in f:
                                        af = f["attributeFilter"]
                                        ident = (af.get("displayForm") or {}).get("identifier") or {}
                                        st.markdown(f"**Filter {i+1}: Attribute** — id: `{ident.get('id', '')}`, type: `{ident.get('type', '')}`, negativeSelection: `{af.get('negativeSelection')}`, localIdentifier: `{af.get('localIdentifier', '')}`")
                                        uris = (af.get("attributeElements") or {}).get("uris") or []
                                        if uris:
                                            st.caption(f"Elements: {uris[:10]}{'...' if len(uris) > 10 else ''}")
                                    else:
                                        st.json(f)
                                else:
                                    st.write(f"Filter {i+1}:", f)
                            st.caption(f"Content version: {content.get('version', 'N/A')}")
                        with st.expander(f"Raw JSON: {title}"):
                            st.code(
                                pretty_json(
                                    fc_dict,
                                    fallback={
                                        "id": selected_fc.get("id", ""),
                                        "title": title,
                                        "content": content,
                                        "description": selected_fc.get("description", ""),
                                    },
                                ),
                                language="json",
                            )
                        if index < len(filter_context_records):
                            st.divider()
                else:
                    st.info("No filter contexts found for the selected dashboard in the current workspace.")
            else:
                st.info("Please select a workspace to view filter contexts.")

        # Handle other content view modes (not Filter Contexts)
        elif dashboard_view_mode != "Filter Contexts":
            if dashboard_view_mode == "Overview":
                if active_ws:
                    st.write(f"**Workspace: {active_ws.name}**")
                    overview_stats = workspace_overview_stats(current_semantics) if current_semantics else {}
                    selected_dashboard_id = st.session_state.get("selected_dashboard_id")
                    selected_dashboard_filter_stats = dashboard_effective_filter_stats(current_semantics, selected_dashboard_id) if selected_dashboard_id else {"filter_context_objects": 0, "effective_filters": 0}
                    automations = get_workspace_automations(st.session_state["gd"], current_ws_id) if current_ws_id else {}
                    schedules = automations.get("schedules", [])
                    alerts = automations.get("alerts", [])

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Dashboards", overview_stats.get("dashboards", 0))
                    with col2:
                        st.metric("Visualizations", overview_stats.get("visualizations", 0))
                    with col3:
                        st.metric("Metrics", overview_stats.get("metrics", 0))
                    with col4:
                        st.metric("Filter Context Objects", overview_stats.get("filter_contexts", 0))

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("AFM Measures", overview_stats.get("afm_measures", 0))
                    with col2:
                        st.metric("AFM Attributes", overview_stats.get("afm_attributes", 0))
                    with col3:
                        st.metric("AFM Filters", overview_stats.get("afm_filters", 0))
                    with col4:
                        st.metric("Selected Dashboard Filters", selected_dashboard_filter_stats.get("effective_filters", 0))

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Dependency Nodes", overview_stats.get("dependency_nodes", 0))
                    with col2:
                        st.metric("Dependency Edges", overview_stats.get("dependency_edges", 0))
                    with col3:
                        st.metric("Schedules", len(schedules))
                    with col4:
                        st.metric("Dashboard Shares", overview_stats.get("dashboard_shares", 0))

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Selected Dashboard FC Objects", selected_dashboard_filter_stats.get("filter_context_objects", 0))
                    with col2:
                        st.metric("Alerts", len(alerts))
                    with col3:
                        st.metric("Selected Dashboard", 1 if selected_dashboard_id else 0)
                    with col4:
                        st.metric("Workspace Filter Objects", overview_stats.get("filter_contexts", 0))

                    st.divider()
                    st.subheader("Overview Summary")
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {"Category": "Dashboards", "Count": overview_stats.get("dashboards", 0)},
                                {"Category": "Visualizations", "Count": overview_stats.get("visualizations", 0)},
                                {"Category": "Metrics", "Count": overview_stats.get("metrics", 0)},
                                {"Category": "Filter Context Objects", "Count": overview_stats.get("filter_contexts", 0)},
                                {"Category": "AFM Measures", "Count": overview_stats.get("afm_measures", 0)},
                                {"Category": "AFM Attributes", "Count": overview_stats.get("afm_attributes", 0)},
                                {"Category": "AFM Filters", "Count": overview_stats.get("afm_filters", 0)},
                                {"Category": "Selected Dashboard Filters", "Count": selected_dashboard_filter_stats.get("effective_filters", 0)},
                                {"Category": "Selected Dashboard FC Objects", "Count": selected_dashboard_filter_stats.get("filter_context_objects", 0)},
                                {"Category": "Dependency Nodes", "Count": overview_stats.get("dependency_nodes", 0)},
                                {"Category": "Dependency Edges", "Count": overview_stats.get("dependency_edges", 0)},
                                {"Category": "Schedules", "Count": len(schedules)},
                                {"Category": "Alerts", "Count": len(alerts)},
                                {"Category": "Dashboard Shares", "Count": overview_stats.get("dashboard_shares", 0)},
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.info("Please select a workspace from the sidebar or set GOODDATA_DEFAULT_WORKSPACE in your environment.")
            elif dashboard_view_mode == "Dependent Entities Graph" and active_ws:
                st.write(f"**Dependent Entities Graph** - {active_ws.name}")
                components.html(
                    html_cytoscape(
                        st.session_state["gd"].build_graph_elements(
                            current_semantics,
                            mode="workspace_dependencies",
                        )
                    ),
                    height=650,
                )
            elif dashboard_view_mode == "Dashboard Schema" and current_semantics:
                ws_dash_list = st.session_state.get("ws_dash_list", "")
                selected_dashboard_id = st.session_state.get("selected_dashboard_id")
                if ws_dash_list and ws_dash_list != "(no dashboards)" and selected_dashboard_id:
                    st.write(f"**Dashboard Schema** - {ws_dash_list}")
                    components.html(
                        html_cytoscape(
                            st.session_state["gd"].build_graph_elements(
                                current_semantics,
                                mode="dashboard_layout",
                                dashboard_id=selected_dashboard_id,
                            )
                        ),
                        height=650,
                    )
                else:
                    st.info("Please select a dashboard from the sidebar.")
            elif dashboard_view_mode == "Dashboard Embed" and active_ws and current_semantics:
                ws_dash_list = st.session_state.get("ws_dash_list", "")
                if ws_dash_list and ws_dash_list != "(no dashboards)":
                    t = time_it()
                    active_dash = st.session_state["gd"].specific(ws_dash_list, of_type="dashboard", by="name", ws_id=current_ws_id)
                    st.write(f"**Embedded Dashboard** - {ws_dash_list}")
                    st.write(f"connecting to GoodData.UI dashboard component on {st.secrets['GOODDATA_HOST']}")
                    # Render GoodData.UI's React-backed web component directly.
                    dashboard_html = html_gooddata_ui_dashboard(
                        host=st.secrets['GOODDATA_HOST'],
                        workspace_id=active_ws.id,
                        dashboard_id=active_dash.id,
                        token=st.secrets['GOODDATA_TOKEN'],
                        height=700,
                    )
                    components.html(dashboard_html, height=700)
                    st.write(f"dashboard loaded in {time_it(t, True)*1000} milliseconds")
                else:
                    st.info("Please select a dashboard from the sidebar.")
            elif dashboard_view_mode == "Dashboard Shares" and active_ws and current_semantics:
                ws_dash_list = st.session_state.get("ws_dash_list", "")
                if ws_dash_list and ws_dash_list != "(no dashboards)":
                    selected_dashboard_id = st.session_state.get("selected_dashboard_id")
                    if not selected_dashboard_id:
                        st.warning("Could not resolve the selected dashboard.")
                    else:
                        rows = rows_from_dashboard_shares(current_semantics, selected_dashboard_id)
                        st.write(f"**Dashboard Shares** - {ws_dash_list}")
                        st.caption("Users and user groups with permissions on this dashboard.")
                        if rows:
                            st.dataframe(pd.DataFrame(rows), width="stretch")
                            components.html(
                                html_cytoscape(
                                    st.session_state["gd"].build_graph_elements(
                                        current_semantics,
                                        mode="shares",
                                        dashboard_id=selected_dashboard_id,
                                    )
                                ),
                                height=650,
                            )
                        else:
                            st.info("No dashboard shares (assignees) for this dashboard.")
                else:
                    st.info("Please select a dashboard from the sidebar to view its shares.")
            elif dashboard_view_mode == "Schedules":
                st.write("**Schedules & Alerts**")
                st.caption("Schedules and alerts for the current workspace (based on your token).")
                if not current_ws_id:
                    st.info("Select a workspace in the sidebar to see its schedules and alerts.")
                else:
                    render_workspace_automation_sections(st.session_state["gd"], current_ws_id)

    # Handle data preparation
    elif st.session_state.get("upload_csv_btn", False):
        uploaded_file = st.session_state.get("uploaded_file")
        if uploaded_file is not None:
            prep_option = st.session_state.get("prep_option", "CSV as SQL dataset")
            if prep_option == "CSV as SQL dataset":
                st.write("Create a new SQL dataset and paste the SQL query (final version should post it directly to the model)")
                st.write(csv_to_sql(uploaded_file))
            elif prep_option == "CSV S3 uploader":
                st.info("[Placeholder] CSV S3 uploader logic will be implemented here.")
            elif prep_option == "LDM preparation":
                st.write("LDM Preparation: Generating request based on CSV fields...")
                st.write(csv_to_ldm_request(uploaded_file))

    # Handle backup
    elif st.session_state.get("backup_btn", False) and active_ws:
        st.session_state["gd"].export(wks_id=active_ws.id, location=Path.cwd())
        exported_path = Path.cwd().joinpath("gooddata_layouts", org.id, "workspaces", active_ws.id, "analytics_model")
        st.write(f"Workspace: {active_ws.name} backed up to /gooddata_layouts/..., below a list of folders")
        for folder in exported_path.iterdir():
            for file in exported_path.joinpath(folder).glob("*.yaml"):
                st.write(file)
    elif st.session_state.get("deploy_users_internal_clicked", False):
        # Reset the flag
        st.session_state["deploy_users_internal_clicked"] = False

        selected_user_workspaces = st.session_state.get("selected_user_workspaces", {})

        if not selected_user_workspaces:
            st.warning("⚠️ No users selected or no workspaces assigned")
        else:
            st.markdown("---")
            st.subheader(f"👥 User Assignment Report ({len(selected_user_workspaces)} user(s))")

            success_count = 0
            error_count = 0
            errors = []

            for user_id, workspace_name in selected_user_workspaces.items():
                try:
                    # Get workspace ID from name
                    workspace_id = st.session_state["gd"].get_id(workspace_name, of_type="workspace")
                    if not workspace_id:
                        raise Exception(f"Workspace '{workspace_name}' not found")

                    st.session_state["gd"].assign_user_to_workspace(user_id, workspace_id, ["VIEW"])
                    st.success(f"✅ Assigned user '{user_id}' to workspace '{workspace_name}'")
                    success_count += 1
                except Exception as e:
                    error_msg = f"Failed to assign user '{user_id}' to workspace '{workspace_name}': {str(e)}"
                    st.error(f"❌ {error_msg}")
                    errors.append(error_msg)
                    error_count += 1

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.metric("✅ Successful", success_count)
            with col2:
                st.metric("❌ Failed", error_count)

            if errors:
                with st.expander("❌ Error Details", expanded=False):
                    for error in errors:
                        st.text(error)

    elif st.session_state.get("deploy_users_testing_clicked", False):
        # Reset the flag
        st.session_state["deploy_users_testing_clicked"] = False

        workspace_id = st.session_state.get("deploy_users_testing_workspace_id", "")
        users_data = st.session_state.get("users_testing", load_users_testing())
        users_list = users_data.get("users", [])
        user_groups_list = users_data.get("userGroups", [])

        if not workspace_id:
            st.warning("⚠️ No workspace selected")
        elif not users_list:
            st.warning("⚠️ No users configured")
        else:
            st.markdown("---")
            st.subheader(f"🧪 Testing Users Deployment Report")

            deployment_result = st.session_state["gd"].deploy_testing_users(workspace_id, users_data)

            if user_groups_list:
                st.write("**Creating User Groups:**")
                for group_result in deployment_result.get("groups", []):
                    if group_result.get("success"):
                        st.success(f"✅ {group_result.get('message')}")
                    else:
                        st.error(f"❌ {group_result.get('message')}")

            st.divider()
            st.write("**Creating/Updating Users:**")
            for user_result in deployment_result.get("users", []):
                if user_result.get("success"):
                    st.success(f"✅ {user_result.get('message')}")
                else:
                    st.error(f"❌ {user_result.get('message')}")

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.metric("✅ Successful", deployment_result.get("success_count", 0))
            with col2:
                st.metric("❌ Failed", deployment_result.get("error_count", 0))

    else:
        # Default view: show workspace info (no auto-generated graph)
        if active_ws:
            st.write(f"**Selected workspace: {active_ws.name}**")
            st.info("Select a dashboard view mode from the sidebar to display content.")
        else:
            st.info("Please select a workspace from the sidebar or set GOODDATA_DEFAULT_WORKSPACE in your environment.")





if __name__ == "__main__":
    main()
