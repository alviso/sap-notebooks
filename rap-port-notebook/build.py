import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The sources are read from a checkout of github.com/alviso/proof-port,
# by default next to this repo. Set PROOF_PORT to point elsewhere.
ROOT = os.path.join(os.environ.get("PROOF_PORT", os.path.join(HERE, "..", "..", "proof-port")), "runs")


def load(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read().replace("\r\n", "\n").rstrip("\n")
    return text.split("\n")


def lang_of(name):
    return "abap" if name.endswith(".abap") else "cds"


# ---------------------------------------------------------------- ZCRED
CR = ROOT + "/ZCRED"
cr_files = [
    dict(id="SAPMZCRED", path=CR + "/extract/source/SAPMZCRED.abap", group="old", adt="PROG",
         role="The old module pool: screens 0100 and 0200, status ZMAIN, every rule in PAI modules and one FORM."),
    dict(id="ZPP_CR_C_CUSTOMER.ddls", path=CR + "/port/src/ZPP_CR_C_CUSTOMER.ddls", group="new", adt="DDLS",
         role="Root view entity over ZCR_CUSTOMER. The BO root and the service's Customer."),
    dict(id="ZPP_CR_C_CHANGELOG.ddls", path=CR + "/port/src/ZPP_CR_C_CHANGELOG.ddls", group="new", adt="DDLS",
         role="View entity over ZCR_CHANGELOG, read only, shown under the customer."),
    dict(id="ZPP_CR_C_LIMITRULE.ddls", path=CR + "/port/src/ZPP_CR_C_LIMITRULE.ddls", group="new", adt="DDLS",
         role="View entity over ZCR_LIMIT_RULE, the reason threshold per currency."),
    dict(id="ZPP_CR_A_SELECT.ddls", path=CR + "/port/src/ZPP_CR_A_SELECT.ddls", group="new", adt="DDLS",
         role="Abstract entity: what screen 0100 asked for."),
    dict(id="ZPP_CR_A_CHANGE.ddls", path=CR + "/port/src/ZPP_CR_A_CHANGE.ddls", group="new", adt="DDLS",
         role="Abstract entity: what screen 0200 asked for."),
    dict(id="ZPP_CR_C_CUSTOMER.bdef", path=CR + "/port/src/ZPP_CR_C_CUSTOMER.bdef", group="new", adt="BDEF",
         role="Behavior definition: managed with additional save, one entity, two actions."),
    dict(id="ZPP_CR_BP_CUSTOMER.clas", path=CR + "/port/src/ZPP_CR_BP_CUSTOMER.clas.abap", group="new", adt="CLAS",
         role="Behavior pool, global part: holds the side buffer for the reason."),
    dict(id="ZPP_CR_BP_CUSTOMER.locals", path=CR + "/port/src/ZPP_CR_BP_CUSTOMER.clas.locals_imp.abap", group="new", adt="CLAS·L",
         role="Behavior pool, local types: handler lhc_customer and saver lsc_zpp_cr_c_customer."),
    dict(id="ZPP_CR_C_CUSTOMER.ddlx", path=CR + "/port/src/ZPP_CR_C_CUSTOMER.ddlx", group="new", adt="DDLX",
         role="Metadata extension: list report columns, object page facets, action buttons."),
    dict(id="ZPP_CR_UI_CREDIT.srvd", path=CR + "/port/src/ZPP_CR_UI_CREDIT.srvd", group="new", adt="SRVD",
         role="Service definition exposing three entities. Bound as OData V4 UI by ZPP_CR_UI_CREDIT_O4."),
]

cr_notes = [
    # old program
    ("SAPMZCRED", "MODULE lock_priority OUTPUT.", 1, 9, "port", "Field control in PBO",
     "`LOOP AT SCREEN` with `screen-input = 0` for a priority customer. Nothing enforces it later; the screen just doesn't offer the field. It became instance feature control plus a fallback in the action."),
    ("SAPMZCRED", "MODULE exit_command INPUT.", 1, 3, "gap", "Dead code",
     "No function code in status ZMAIN is an exit command, so `AT EXIT-COMMAND` never runs. The oracle confirmed it: EXIT on 0100 still looks the customer up and goes to 0200."),
    ("SAPMZCRED", "CHECK ok_code = 'SAVE'.", 1, 1, "port", "Enter does nothing",
     "On Enter the module ends here, so the driver only calls the action on SAVE. The dynpro still converts the typed number on every press, so a bad number is refused on Enter too."),
    ("SAPMZCRED", "IF gv_new_limit < 0.", 1, 3, "gap", "A check no screen can reach",
     "`gv_new_limit` sits on an unsigned dynpro field, so `-100` is refused with 'Specify positive values only' before this module runs."),
    ("SAPMZCRED", "UPDATE zcr_customer FROM gs_cust.", 1, 3, "port", "Save without a lock",
     "No ENQUEUE anywhere: two users can overwrite each other, and the log then shows the same old limit twice. A failing INSERT is ignored and COMMIT WORK commits the customer anyway."),
    ("SAPMZCRED", "FORM f4_customer.", 2, 1, "gap", "F4 help",
     "A hand-built value list with headings the table doesn't have. The list report shows the same columns. Batch input can't press F4, so nothing grades it."),
    # CDS customer
    ("ZPP_CR_C_CUSTOMER.ddls", "define root view entity ZPP_CR_C_CUSTOMER", 1, 2, "review", "One view does every job",
     "Root view entity straight on the table. No interface view under it, no projection view or projection BDEF over it. The `C_` prefix suggests a consumption view, but this one view is the BO, the service entity and the UI entity. A reviewer will ask for `R_` plus `C_` with a projection BDEF."),
    ("ZPP_CR_C_CUSTOMER.ddls", "@AccessControl.authorizationCheck: #NOT_REQUIRED", 1, 1, "gap", "No read authorization",
     "No DCL role, so anyone who reaches the service reads every customer's limit. The old transaction was guarded by S_TCODE on ZCRED. The BDEF has no authorization master either, so writes are open too. A comparison that runs as one user can't see this."),
    ("ZPP_CR_C_CUSTOMER.ddls", "association [0..*] to ZPP_CR_C_CHANGELOG", 1, 1, "rap", "Association, not composition",
     "The change log is context, not part of the BO: it doesn't lock or save with the customer. It is exposed so the object page can list it. The log row itself is written by the additional save, outside the managed buffer."),
    ("ZPP_CR_C_CUSTOMER.ddls", "@Semantics.amount.currencyCode: 'Currency'", 1, 2, "rap", "Amount with a currency reference",
     "The UI shows the currency beside the amount and the V4 metadata gets a currency annotation. The old `gv_new_limit` was P(8) DECIMALS 2 with no currency reference, so neither side shifts decimals per TCURX. Same behaviour; fine for EUR or USD, and the question to ask for JPY."),
    ("ZPP_CR_C_CUSTOMER.ddls", "case priority", 1, 4, "port", "Field control as data",
     "CreditLimitFc carries MODULE lock_priority into the service: 1 for a priority customer. In the OData FieldControlType vocabulary 0 is hidden, 1 read-only, 3 optional and 7 mandatory, so 7 says more than editable. No annotation ties it to CreditLimit, so Fiori ignores it and uses the BDEF's instance feature control. It is a contract for the agent's driver."),
    # BDEF
    ("ZPP_CR_C_CUSTOMER.bdef", "managed with additional save", 1, 1, "rap", "Managed with additional save",
     "The framework owns the buffer and writes ZCR_CUSTOMER through the mapping. `with additional save` opens `save_modified` in the saver for the change log INSERT, in the same LUW. No `strict ( 2 )`: strict mode would reject a root without an authorization master."),
    ("ZPP_CR_C_CUSTOMER.bdef", "lock master", 1, 1, "review", "Locked, but no ETag",
     "A pessimistic lock that, in stateless OData, lives for one request. There is no `etag master`, so nothing checks that the row is unchanged between reading the object page and pressing the action. The action re-reads the row, so the log's old limit is right, but a user can still decide on a stale screen."),
    ("ZPP_CR_C_CUSTOMER.bdef", "field ( readonly ) CustomerName", 1, 1, "rap", "Readonly binds callers only",
     "Code running IN LOCAL MODE can still write these fields. That is how blockWhenZero sets Blocked."),
    ("ZPP_CR_C_CUSTOMER.bdef", "field ( features : instance ) CreditLimit;", 1, 1, "rap", "Dynamic field control",
     "Answered per instance by `get_instance_features`, so the UI shows the limit read-only for a priority customer. IN LOCAL MODE doesn't consult it, which matters in the action."),
    ("ZPP_CR_C_CUSTOMER.bdef", "internal update;", 1, 1, "port", "The action is the only door",
     "`update` exists only for the BO's own EML and is absent from the service metadata, so no PATCH can set CreditLimit. Same as the old program, which changes a limit only on SAVE."),
    ("ZPP_CR_C_CUSTOMER.bdef", "static action ChooseCustomer", 1, 1, "review", "A check modelled as an action",
     "Screen 0100 becomes a static action that changes nothing and only answers with messages. A static function is the idiomatic shape for a side-effect-free check, so expect the question. A fair answer: every old screen step must be a call that can fail with the old E message, and failed/reported does that directly."),
    ("ZPP_CR_C_CUSTOMER.bdef", "action ChangeCreditLimit parameter ZPP_CR_A_CHANGE;", 1, 1, "rap", "Instance action, no result",
     "Parameter typed by an abstract entity. No result is declared, so the call returns HTTP 204 and the old S message 'Credit limit changed' is gone; Fiori shows its own toast."),
    ("ZPP_CR_C_CUSTOMER.bdef", "determination blockWhenZero on modify", 1, 1, "port", "Zero blocks the customer",
     "FORM save_change set `blocked = 'X'` at save time. Here it runs on modify, right after the action's update, because CreditLimit is its trigger field."),
    ("ZPP_CR_C_CUSTOMER.bdef", "validation checkChange on save", 1, 1, "rap", "Triggered by the request",
     "A field trigger fires when CreditLimit is in an update request (its `%control` flag), whether or not the value differs. That is what lets 'Credit limit is unchanged' fire."),
    ("ZPP_CR_C_CUSTOMER.bdef", "mapping for zcr_customer", 1, 1, "rap", "Mapping",
     "CamelCase CDS names to table fields for the managed save. CreditLimitFc has no mapping: computed, never stored."),
    # class global
    ("ZPP_CR_BP_CUSTOMER.clas", "FOR BEHAVIOR OF zpp_cr_c_customer.", 1, 1, "rap", "Behavior pool shell",
     "ABSTRACT FINAL, no logic in the global class. The handler (`lhc_`) and saver (`lsc_`) live in the local types."),
    ("ZPP_CR_BP_CUSTOMER.clas", "CLASS-DATA pending", 1, 1, "review", "A side buffer in a managed BO",
     "The reason has no column in ZCR_CUSTOMER, so it can't ride in the managed buffer. The action puts it here, the validation completes it, `save_modified` writes the log row from it. It works, but it is unmanaged-style state in a managed BO. Cleaner: make the change log a composition child and create the row by association in the action, so the managed save writes it and neither the additional save nor this buffer is needed."),
    # locals
    ("ZPP_CR_BP_CUSTOMER.locals", "METHODS get_instance_features FOR INSTANCE FEATURES", 1, 2, "rap", "Methods by declaration",
     "Each BDEF feature has its handler signature: FOR INSTANCE FEATURES, FOR MODIFY ... FOR ACTION, FOR DETERMINE ON MODIFY, FOR VALIDATE ON SAVE. The comments name the old module each one replaces."),
    ("ZPP_CR_BP_CUSTOMER.locals", "%field-CreditLimit = COND #", 1, 3, "rap", "Feature control result",
     "`if_abap_behv=>fc-f-read_only` or `unrestricted` per key, from Priority read IN LOCAL MODE."),
    ("ZPP_CR_BP_CUSTOMER.locals", "WHERE kunnr = @ls_key-%param-Customer", 1, 1, "review", "SQL inside a handler",
     "A direct SELECT instead of READ ENTITIES. For a static check there is no instance to read, so it is reasonable, but it reads the database, not the transactional buffer."),
    ("ZPP_CR_BP_CUSTOMER.locals", "APPEND VALUE #( %cid = ls_key-%cid ) TO failed-customer.", 1, 1, "rap", "No key, so %cid",
     "A static action has no instance, so failed and reported are keyed by `%cid`. In ChangeCreditLimit they are keyed by Customer."),
    ("ZPP_CR_BP_CUSTOMER.locals", "IF ls_customer-priority = c_priority.", 1, 4, "port", "The priority fallback",
     "A display-only dynpro field still holds what was loaded. So for a priority customer the new limit is forced back to the stored one, and the validation answers 'Credit limit is unchanged', as the old screen did. Needed because the MODIFY below runs IN LOCAL MODE and skips feature control."),
    ("ZPP_CR_BP_CUSTOMER.locals", "DELETE zpp_cr_bp_customer=>pending WHERE kunnr", 1, 7, "port", "Carrying the reason",
     "Old `gv_reason` lived between screen 0200 and FORM save_change. The action keeps it in the side buffer, keyed by customer, with `checked` still false."),
    ("ZPP_CR_BP_CUSTOMER.locals", "MODIFY ENTITIES OF zpp_cr_c_customer IN LOCAL MODE", 1, 7, "rap", "EML IN LOCAL MODE",
     "The BO calling itself. IN LOCAL MODE skips feature control and authorization checks, and it is the only way to use an internal update. The inner FAILED and REPORTED are appended to the action's own."),
    ("ZPP_CR_BP_CUSTOMER.locals", "IF ls_customer-CreditLimit = 0 AND ls_customer-Blocked <> c_blocked.", 1, 1, "rap", "No self-retrigger",
     "The determination writes only Blocked, which is not its trigger field, so it can't fire itself again."),
    ("ZPP_CR_BP_CUSTOMER.locals", "WHERE kunnr = @ls_customer-Customer", 1, 2, "port", "Compared against the database",
     "The old module compared against `gs_cust`, loaded on 0100, so the validation reads the database row, not the buffer. A side effect: Blocked is also checked from the database, so blockWhenZero having set it in the buffer doesn't make this validation fail."),
    ("ZPP_CR_BP_CUSTOMER.locals", "ELSEIF ls_customer-CreditLimit < 0.", 1, 1, "gap", "Kept for API callers",
     "Unreachable from a screen (the dynpro field is unsigned), kept so an API caller posting a negative limit gets the old text. No graded case can show it."),
    ("ZPP_CR_BP_CUSTOMER.locals", "IF ls_customer-CreditLimit > lv_threshold AND lv_reason IS INITIAL.", 1, 1, "port", "No rule means zero",
     "Same SELECT SINGLE as before; no row leaves the threshold at zero, so in a currency without a rule every positive limit needs a reason. Faithful, quirk included. A reason of blanks counts as none, as IS INITIAL does."),
    ("ZPP_CR_BP_CUSTOMER.locals", "text     = lv_text ) ) TO reported-customer.", 1, 1, "review", "Free-text messages",
     "`new_message_with_text` has no message class. The OData error shows SABP_BEHV/100 where `MESSAGE '...' TYPE 'E'` gave 00/001: the texts match, the ids don't. Production code would use a T100 message class with `new_message( )`, or an exception class implementing `if_abap_behv_message`."),
    ("ZPP_CR_BP_CUSTOMER.locals", "METHOD save_modified.", 1, 1, "rap", "Additional save",
     "Runs in the save sequence after the validations passed; `update-customer` holds the instances the framework is writing. One LUW: if the log INSERT fails, the customer update rolls back too. The old program committed the customer and silently lost the log row."),
    ("ZPP_CR_BP_CUSTOMER.locals", "INSERT zcr_changelog FROM @ls_log.", 1, 1, "review", "Unchecked INSERT",
     "sy-subrc is ignored, as in the old FORM. In RAP that is also the expected shape: the save phase must not fail, and anything that can go wrong belongs in a validation before it."),
    ("ZPP_CR_BP_CUSTOMER.locals", "METHOD cleanup_finalize.", 1, 4, "review", "Who clears the buffer?",
     "`cleanup_finalize` runs when the save is rejected in finalize or check_before_save. After a successful save nothing clears `pending`. Harmless in stateless OData, where each request is a new session; a latent leak for an EML caller that commits twice in one session."),
    # ddlx, srvd, abstract
    ("ZPP_CR_C_CUSTOMER.ddlx", "@Metadata.layer: #CORE", 1, 1, "rap", "Layer",
     "CORE is the lowest layer; LOCALIZATION, INDUSTRY, PARTNER and CUSTOMER layers can override it without touching this file."),
    ("ZPP_CR_C_CUSTOMER.ddlx", "dataAction: 'ChooseCustomer'", 0, 2, "rap", "Buttons from annotations",
     "#FOR_ACTION entries in lineItem put the actions on the list report toolbar; the identification entry puts ChangeCreditLimit on the object page. A static action needs no selected row."),
    ("ZPP_CR_C_CUSTOMER.ddlx", "targetElement: '_Log'", 1, 1, "rap", "Facet over an association",
     "A LINEITEM_REFERENCE facet on `_Log` lists the customer's changes. Its columns come from the @UI.lineItem annotations inside ZPP_CR_C_CHANGELOG itself."),
    ("ZPP_CR_C_CUSTOMER.ddlx", "CreditLimitFc;", 1, 1, "rap", "Hidden, still in the payload",
     "@UI.hidden keeps it off the screen but in the entity, which is how the driver reads it."),
    ("ZPP_CR_UI_CREDIT.srvd", "expose ZPP_CR_C_LIMITRULE as LimitRule;", 1, 1, "rap", "Read-only entity",
     "LimitRule has no behavior definition, so it is exposed read-only. The binding publishes all three under `/sap/opu/odata4/sap/zpp_cr_ui_credit_o4/srvd/sap/zpp_cr_ui_credit/0001/`."),
    ("ZPP_CR_A_CHANGE.ddls", "define abstract entity ZPP_CR_A_CHANGE", 1, 1, "rap", "Abstract entity as a parameter",
     "No table and no SQL view; it only types the action parameter. The V4 adapter refused NewLimit sent as the string '7000.00' and wanted a JSON number: Edm.Decimal travels as a string only when the request declares IEEE754Compatible=true."),
    ("ZPP_CR_A_SELECT.ddls", "Customer : abap.char(10);", 1, 1, "port", "Same width as the screen field",
     "CHAR 10 like GV_KUNNR. The tables are built-in typed, so there is no ALPHA conversion on either side."),
]

cr_rules = [
    ("Customer not found",
     ("SAPMZCRED", "MESSAGE 'Customer not found' TYPE 'E'.", 1, 1),
     ("ZPP_CR_BP_CUSTOMER.locals", "SELECT SINGLE * FROM zcr_customer", 1, 10),
     "MODULE check_customer becomes the static action ChooseCustomer: same SELECT SINGLE, same text, keyed by `%cid`."),
    ("Customer is blocked",
     ("SAPMZCRED", "IF gs_cust-blocked = 'X'.", 1, 3),
     ("ZPP_CR_BP_CUSTOMER.locals", "IF ls_customer-blocked = c_blocked.", 1, 7),
     "Same check in the action. It is also the first check of the validation, so an API caller that skips ChooseCustomer still gets it."),
    ("Priority customer: limit is display only",
     ("SAPMZCRED", "MODULE lock_priority OUTPUT.", 1, 9),
     ("ZPP_CR_BP_CUSTOMER.locals", "METHOD get_instance_features.", 1, 15),
     "PBO screen modification becomes instance feature control. The action adds its own fallback, because IN LOCAL MODE skips feature control."),
    ("Limit unchanged",
     ("SAPMZCRED", "IF gv_new_limit = gs_cust-credit_limit.", 1, 3),
     ("ZPP_CR_BP_CUSTOMER.locals", "ELSEIF ls_customer-CreditLimit = ls_db-credit_limit.", 1, 2),
     "Compared against the database row, as the old module compared against what 0100 loaded. The validation fires because CreditLimit is in the request, even with the same value."),
    ("Reason required above the threshold",
     ("SAPMZCRED", "SELECT SINGLE threshold FROM zcr_limit_rule INTO lv_threshold", 1, 6),
     ("ZPP_CR_BP_CUSTOMER.locals", "SELECT SINGLE threshold FROM zcr_limit_rule", 1, 6),
     "Same lookup, same 'no row means zero'. The reason comes from the side buffer the action filled."),
    ("Zero blocks the customer",
     ("SAPMZCRED", "IF gv_new_limit = 0.", 1, 3),
     ("ZPP_CR_BP_CUSTOMER.locals", "METHOD blockwhenzero.", 1, 25),
     "Moved from the save FORM to a determination on modify, triggered by CreditLimit."),
    ("Write the customer",
     ("SAPMZCRED", "UPDATE zcr_customer FROM gs_cust.", 1, 1),
     ("ZPP_CR_C_CUSTOMER.bdef", "mapping for zcr_customer", 1, 9),
     "No UPDATE statement in the port: the managed runtime writes the row through `persistent table` and the mapping."),
    ("Write the change log",
     ("SAPMZCRED", "FORM save_change.", 2, 22),
     ("ZPP_CR_BP_CUSTOMER.locals", "METHOD save_modified.", 1, 25),
     "The log INSERT moves into the additional save, inside the same LUW as the customer update."),
]

# ---------------------------------------------------------------- ZMM01
MM = ROOT + "/ZMM01"
mm_files = [
    dict(id="SAPMZRET_ART", path=MM + "/extract/source/SAPMZRET_ART.abap", group="old", adt="PROG",
         role="Module pool frame: four includes. Transaction ZMM01, screens 0100, 0200, 0210, 0220, 0230."),
    dict(id="MZRET_ARTTOP", path=MM + "/extract/source/MZRET_ARTTOP.abap", group="old", adt="INCL",
         role="Globals: TABLES screen structures, the tabstrip and the table control."),
    dict(id="MZRET_ARTO01", path=MM + "/extract/source/MZRET_ARTO01.abap", group="old", adt="INCL",
         role="PBO modules: status, title, active tab, listbox values, table control lines."),
    dict(id="MZRET_ARTI01", path=MM + "/extract/source/MZRET_ARTI01.abap", group="old", adt="INCL",
         role="PAI modules: the subscreen checks and the function codes."),
    dict(id="MZRET_ARTF01", path=MM + "/extract/source/MZRET_ARTF01.abap", group="old", adt="INCL",
         role="FORMs: load_article, check_all, save_article."),
    dict(id="ZPP_MM_R_ARTICLE.ddls", path=MM + "/port/src/ZPP_MM_R_ARTICLE.ddls", group="new", adt="DDLS",
         role="Root view entity over ZRET_T_ARTICLE, composition of the variants."),
    dict(id="ZPP_MM_R_VARIANT.ddls", path=MM + "/port/src/ZPP_MM_R_VARIANT.ddls", group="new", adt="DDLS",
         role="Child view entity over ZRET_T_ART_VAR."),
    dict(id="ZPP_MM_P_SAVE.ddls", path=MM + "/port/src/ZPP_MM_P_SAVE.ddls", group="new", adt="DDLS",
         role="Abstract entity: one screenful, the parameter of pressSave."),
    dict(id="ZPP_MM_R_ARTICLE.bdef", path=MM + "/port/src/ZPP_MM_R_ARTICLE.bdef", group="new", adt="BDEF",
         role="Behavior definition: managed, strict ( 2 ), parent and child."),
    dict(id="ZPP_MM_BP_ARTICLE.clas", path=MM + "/port/src/ZPP_MM_BP_ARTICLE.clas.abap", group="new", adt="CLAS",
         role="Behavior pool, global part. Empty by design."),
    dict(id="ZPP_MM_BP_ARTICLE.locals", path=MM + "/port/src/ZPP_MM_BP_ARTICLE.clas.locals_imp.abap", group="new", adt="CLAS·L",
         role="Behavior pool, local types: authorization, one determination, one validation, the Save action."),
    dict(id="ZPP_MM_X_ARTICLE.ddlx", path=MM + "/port/src/ZPP_MM_X_ARTICLE.ddlx", group="new", adt="DDLX",
         role="Metadata extension: the three tabs became three sections of one object page."),
    dict(id="ZPP_MM_X_VARIANT.ddlx", path=MM + "/port/src/ZPP_MM_X_VARIANT.ddlx", group="new", adt="DDLX",
         role="Metadata extension of the variant table."),
    dict(id="ZPP_MM_UI_ARTICLE.srvd", path=MM + "/port/src/ZPP_MM_UI_ARTICLE.srvd", group="new", adt="SRVD",
         role="Service definition. Bound as OData V4 UI by ZPP_MM_UI_ARTICLE_O4."),
]

mm_notes = [
    # old
    ("MZRET_ARTI01", "MODULE check_0210 INPUT.", 1, 13, "port", "Subscreen PAI",
     "Runs only for the visible subscreen, and before user_command_0200 calls check_all. The default `ST` is set only after the checks pass. This ordering is why the port needs SaveTab."),
    ("MZRET_ARTI01", "CALL FUNCTION 'POPUP_TO_CONFIRM'", 1, 1, "gap", "A popup nobody sees",
     "Back, Exit and Cancel are not exit commands in this screen's status, so `exit_0200` never runs. On 0200 those codes do nothing at all and a later Save still works. The port copies what the screen does, not the popup."),
    ("MZRET_ARTO01", "MODULE init_listbox OUTPUT.", 1, 1, "gap", "The listbox and the domain disagree",
     "The list offers HARD, SOFT, FOOD; the domain's fixed values are HARD, SOFT, ACCE, CONS. Food is rejected, ACCE and CONS are accepted unseen. The new app takes its values from the domain, so here it is deliberately not identical."),
    ("MZRET_ARTF01", "MOVE-CORRESPONDING zret_s_art TO ls_art.", 1, 1, "gap", "Wholesale overwrite",
     "The screen structure has no COLOR or ART_SIZE, so the MODIFY below clears them on every change. The port doesn't copy that."),
    ("MZRET_ARTF01", "DELETE FROM zret_t_art_var WHERE article_id = ls_art-article_id.", 1, 5, "gap", "A dead error branch",
     "sy-subrc is forced to 0 before the INSERT. A duplicate variant id doesn't return 4: INSERT FROM TABLE dumps with SAPSQL_ARRAY_INSERT_DUPREC. So ROLLBACK WORK and message e05 can never happen. The BO refuses the duplicate with the framework's message and writes nothing."),
    # cds
    ("ZPP_MM_R_ARTICLE.ddls", "composition [0..*] of ZPP_MM_R_VARIANT as _Variant", 1, 1, "rap", "Composition",
     "Variants are part of the article: they lock, authorize and save with it, and are created through it."),
    ("ZPP_MM_R_ARTICLE.ddls", "as BaseUom", 1, 1, "port", "Units and the logon language",
     "BASE_UOM has the CUNIT conversion exit on the old screen. The service also takes the unit in the logon language's spelling (PC in English for internal ST) and rejects unknown ones. They matched because both sides ran in English; across languages it is untested."),
    ("ZPP_MM_R_ARTICLE.ddls", "cast( '' as abap.char( 4 ) ) as SaveTab", 1, 1, "review", "Screen state inside the BO",
     "Which tab was open at Save. The open subscreen's PAI ran before check_all, so the tab decides which message comes first and which default fills in. Not persisted; the BDEF activates with a warning about the missing mapping. Faithful to the dynpro, but it is dynpro state in a BO. Expect: would you keep it in production?"),
    ("ZPP_MM_R_VARIANT.ddls", "association to parent ZPP_MM_R_ARTICLE as _Article", 1, 1, "rap", "To-parent association",
     "The other half of the composition. Required for `lock dependent` and `authorization dependent`."),
    ("ZPP_MM_R_VARIANT.ddls", "cast( 0 as abap.int4 ) as ScreenRow", 1, 1, "port", "The row travels with the line",
     "Old messages name the table control row ('Variante ligne 3'). After a deletion rows shift up, so the number has to come with the data. A row a person adds in the app has 0, and the validation falls back to its position."),
    ("ZPP_MM_P_SAVE.ddls", "Row1VariantId", 1, 5, "review", "Six flat rows",
     "The old table control shows six lines, so the parameter has six flat rows read with ASSIGN COMPONENT. RAP can also type a deep action parameter (an abstract entity with a composition); the agent didn't try it, and it might meet the same nested-payload refusal as the deep insert."),
    # bdef
    ("ZPP_MM_R_ARTICLE.bdef", "managed implementation in class zpp_mm_bp_article unique;", 1, 2, "rap", "Managed, strict ( 2 )",
     "Strict mode tightens the syntax check: authorization control is mandatory, deprecated syntax is refused, `%tky` is the expected key. Compare ZCRED, which is not strict and has no authorization master."),
    ("ZPP_MM_R_ARTICLE.bdef", "lock master", 1, 1, "review", "No ETag",
     "lock master without etag master. The tables only have CHANGED_ON as a date, which can't serve as an ETag; a real port adds a timestamp column, or uses draft with a total etag."),
    ("ZPP_MM_R_ARTICLE.bdef", "authorization master ( global )", 1, 1, "gap", "Present, but open",
     "Strict mode demanded it, so it is there, and `get_global_authorizations` allows create, update and delete for everyone. The old ZMM01 checked no authority object either."),
    ("ZPP_MM_R_ARTICLE.bdef", "update;", 1, 1, "gap", "Changing an existing article",
     "Deliberately different. The old FORM overwrote the header from the screen (clearing COLOR and ART_SIZE) and deleted and reinserted every variant. The BO updates fields and variants one by one. The agent judged the old behaviour data loss. No graded case reaches it: every graded save was a create."),
    ("ZPP_MM_R_ARTICLE.bdef", "field ( mandatory : create ) ArticleId;", 1, 2, "rap", "External key, frozen after create",
     "The key is typed on create and can't change after. The old required field on 0100 became `mandatory : create`; the old e01 message is unreachable on both sides."),
    ("ZPP_MM_R_ARTICLE.bdef", "determination prepareSave on modify", 1, 2, "review", "On modify, and the stated reason",
     "One determination does the tab default, variant currency, header EAN and admin stamps, in the old FORM's order. Its triggers exclude the fields it writes, so it can't retrigger itself. The comment says an on-save determination may not write its own buffer; that isn't the general rule (stamping admin fields on save is the textbook case), and on-save determinations also run before validations. Be ready to defend or change it."),
    ("ZPP_MM_R_ARTICLE.bdef", "validation checkArticle on save { create; update; }", 1, 1, "rap", "Operation triggers",
     "Fires on every create and update, no field list. The variants have no validation of their own; the root checks them by reading `_Variant`."),
    ("ZPP_MM_R_ARTICLE.bdef", "static action pressSave parameter ZPP_MM_P_SAVE;", 1, 1, "port", "Save as an action",
     "The natural V4 shape is a deep insert: POST the article with nested variants. This system refused any nested payload, because the V4 runtime treats it as an upload and wants virus scan profile /IWBEP/V4/ODATA_UPLOAD active (SAP note 3027559). Activating it was outside the agent's namespace, so Save became one static action. Draft would be the other way out."),
    ("ZPP_MM_R_ARTICLE.bdef", "association _Variant { create; }", 1, 1, "rap", "Create by association",
     "Variants are created only through the article. The variant entity has update and delete, no create of its own."),
    ("ZPP_MM_R_ARTICLE.bdef", "lock dependent by _Article", 1, 2, "rap", "Dependent lock and authorization",
     "The child follows the root: locking a variant locks its article, and the article's authorization decides."),
    # locals
    ("ZPP_MM_BP_ARTICLE.locals", "METHOD get_global_authorizations.", 1, 11, "gap", "Allow everything",
     "Global authorization answers per operation before any instance is read. Here every request gets `auth-allowed`. A real port runs AUTHORITY-CHECK on an authorization object here, or moves to instance authorization if access depends on the article."),
    ("ZPP_MM_BP_ARTICLE.locals", "ENTITY article BY \\_variant", 1, 2, "rap", "Read by association with %tky",
     "`%tky` is the transactional key: the key fields plus `%is_draft` once draft is on. strict ( 2 ) pushes it over plain keys, so this code survives adding draft later."),
    ("ZPP_MM_BP_ARTICLE.locals", "IF ls_article-savetab = 'TAB1' AND lv_base_uom IS INITIAL.", 1, 6, "port", "Defaults from the open tab only",
     "check_0210 and check_0220 ran only for the visible subscreen. Clear the base unit, save from the Price tab, and it stays empty in the database, on both sides. A person on the object page can't produce that row, since there are no tabs."),
    ("ZPP_MM_BP_ARTICLE.locals", "WHERE currency IS INITIAL.", 1, 1, "port", "Variant currency",
     "A variant without a currency takes the header's, as FORM save_article did. It uses the defaulted header currency, so the order inside this determination matters."),
    ("ZPP_MM_BP_ARTICLE.locals", "lv_ean = ls_variant-ean.", 1, 2, "port", "Header EAN",
     "The first variant with an EAN, in row order. The old code only filled it IF the header EAN was initial, but the screen structure carries none, so in practice every save re-derives it. The port does the same."),
    ("ZPP_MM_BP_ARTICLE.locals", "IF lv_created_by IS INITIAL AND lv_created_on IS INITIAL.", 1, 4, "review", "Admin stamps by hand",
     "Managed RAP can fill admin fields from @Semantics annotations. The user fields would qualify; the date fields don't, because the systemDateTime annotations expect timestamps. Doing all four by hand keeps them together."),
    ("ZPP_MM_BP_ARTICLE.locals", "IF ls_article-savetab = 'TAB2' AND ls_article-price <= 0.", 1, 3, "port", "Message order from the open tab",
     "From the Price tab a bad price is reported before a missing name, because that subscreen's PAI ran first. From the other tabs check_all's order applies: name, type, price, then variants."),
    ("ZPP_MM_BP_ARTICLE.locals", "lv_text = |Variante ligne { lv_row } : identifiant manquant|.", 1, 1, "review", "One message, by design",
     "The old screen stops at the first E message, so the validation reports exactly one. Idiomatic RAP collects every problem in one round trip. Faithful wins here because the grader compares the first message, which also means only the first one is ever tested."),
    ("ZPP_MM_BP_ARTICLE.locals", "strlen( ls_variant-ean ) <> 13", 1, 1, "port", "Same EAN check",
     "Thirteen digits, character by character. No check digit validation, on either side."),
    ("ZPP_MM_BP_ARTICLE.locals", "APPEND VALUE #( %tky = ls_article-%tky ) TO failed-article.", 1, 5, "rap", "failed and reported",
     "failed marks the instance as rejected, which stops the save; reported carries the message with `%tky`, so the UI attaches it to the right object."),
    ("ZPP_MM_BP_ARTICLE.locals", "METHOD presssave.", 1, 1, "rap", "One screenful in one MODIFY",
     "CREATE plus CREATE BY \\_variant in one EML statement. `%cid` names the new article and `%cid_ref` links each variant to it before any key exists in the database."),
    ("ZPP_MM_BP_ARTICLE.locals", "ASSIGN COMPONENT |ROW{ lv_row }VARIANTID|", 1, 5, "rap", "Dynamic component access",
     "Reads Row1 to Row6 by name. A line with no id and no EAN is skipped, as the old loop's CHECK did."),
    ("ZPP_MM_BP_ARTICLE.locals", "failed   = CORRESPONDING #( DEEP lt_failed ).", 1, 2, "review", "Where the validation messages come from",
     "MODIFY returns only what create itself found, such as a duplicate key. checkArticle doesn't run here; it runs in the save sequence of the same OData request, and its messages reach the caller from there. The comment is right at request level, not at this statement."),
    # ddlx
    ("ZPP_MM_X_ARTICLE.ddlx", "@UI.facet: [", 1, 8, "port", "Tabs became sections",
     "Basic data as identification, Price as a field group, Variants as a line item facet on `_Variant`. Nothing is hidden behind a tab any more, which is exactly why the tab-dependent rules can't happen to a person using the app."),
    ("ZPP_MM_X_ARTICLE.ddlx", "SaveTab;", 1, 1, "rap", "Hidden screen state",
     "In the entity for the driver and the determination, never shown."),
]

mm_rules = [
    ("Name, type and price checks",
     ("MZRET_ARTF01", "FORM check_all.", 1, 14),
     ("ZPP_MM_BP_ARTICLE.locals", "IF ls_article-savetab = 'TAB2' AND ls_article-price <= 0.", 1, 12),
     "check_all's order, with the open subscreen's own check first. The validation stops at the first message, as the E message did."),
    ("Price tab checks first",
     ("MZRET_ARTI01", "MODULE check_0220 INPUT.", 1, 10),
     ("ZPP_MM_BP_ARTICLE.locals", "IF ls_article-savetab = 'TAB2' AND ls_article-price <= 0.", 1, 3),
     "The subscreen's PAI ran before check_all. SaveTab carries which tab that was."),
    ("Variant row checks",
     ("MZRET_ARTF01", "LOOP AT gt_var INTO gs_var.", 1, 12),
     ("ZPP_MM_BP_ARTICLE.locals", "LOOP AT lt_variant INTO DATA(ls_variant).", 1, 19),
     "Same loop, same skip rule, same messages with the row number. ScreenRow keeps the number right after rows shift."),
    ("Default base unit ST",
     ("MZRET_ARTI01", "zret_s_art-base_uom = 'ST'.", 1, 1),
     ("ZPP_MM_BP_ARTICLE.locals", "IF ls_article-savetab = 'TAB1' AND lv_base_uom IS INITIAL.", 1, 3),
     "Only when Save was pressed on the Basic data tab, as before."),
    ("Variant currency from the header",
     ("MZRET_ARTF01", "IF ls_var-currency IS INITIAL. ls_var-currency = ls_art-currency. ENDIF.", 1, 1),
     ("ZPP_MM_BP_ARTICLE.locals", "WHERE currency IS INITIAL.", 1, 10),
     "From the save FORM to the determination, as an EML update of the child instances."),
    ("Header EAN",
     ("MZRET_ARTF01", "IF ls_art-ean IS INITIAL.", 1, 6),
     ("ZPP_MM_BP_ARTICLE.locals", "DATA lv_ean TYPE zret_t_article-ean.", 1, 8),
     "The first variant with an EAN becomes the header's."),
    ("Created and changed stamps",
     ("MZRET_ARTF01", "IF gv_exists = abap_true.", 1, 9),
     ("ZPP_MM_BP_ARTICLE.locals", "DATA(lv_created_by) = ls_article-createdby.", 1, 7),
     "Created by and on survive a change; changed by and on are always stamped. Set by hand in the determination."),
    ("Save the screenful",
     ("MZRET_ARTI01", "WHEN 'SAVE'.", 1, 3),
     ("ZPP_MM_BP_ARTICLE.locals", "CREATE FIELDS ( articleid articlename", 1, 9),
     "One function code, one EML statement: the article and its variant rows together, checks in the save sequence."),
    ("Write both tables",
     ("MZRET_ARTF01", "MODIFY zret_t_article FROM ls_art.", 1, 6),
     ("ZPP_MM_R_ARTICLE.bdef", "mapping for zret_t_article", 1, 18),
     "The managed runtime writes both tables through the mappings. On a change it updates rows one by one instead of the old delete and reinsert."),
]

kw_abap = """CLASS DEFINITION IMPLEMENTATION INHERITING FROM PUBLIC PRIVATE PROTECTED SECTION ABSTRACT FINAL FOR BEHAVIOR OF
METHODS METHOD ENDMETHOD ENDCLASS IMPORTING REQUEST RESULT ACTION MODIFY DETERMINE ON VALIDATE SAVE INSTANCE FEATURES
GLOBAL AUTHORIZATION READ ENTITIES ENTITY IN LOCAL MODE FIELDS WITH CORRESPONDING VALUE DATA TYPE TYPES BEGIN END
CONSTANTS LOOP AT INTO ENDLOOP IF ELSEIF ELSE ENDIF CONTINUE EXIT APPEND TO SELECT SINGLE WHERE UPDATE INSERT DELETE
TABLE SORTED UNIQUE KEY COND WHEN THEN REDEFINITION FAILED REPORTED CLEAR ASSIGNING SYMBOL GET TIME STAMP FIELD
AND OR NOT IS INITIAL LINES DO TIMES ENDDO ASSIGN COMPONENT STRUCTURE CREATE BY DEEP LIKE LINE SORT PROGRAM MODULE
ENDMODULE OUTPUT INPUT SET STATUS SCREEN LEAVE MESSAGE PERFORM FORM ENDFORM USING CHECK COMMIT WORK ROLLBACK CALL
FUNCTION EXPORTING TABLES EXCEPTIONS OTHERS CASE ENDCASE INCLUDE CONTROLS TABSTRIP TABLEVIEW TITLEBAR WHILE ENDWHILE
DESCRIBE MOVE RETURN LENGTH DECIMALS STANDARD ORDER CN INDEX FIELDS""".split()

kw_cds = """define root view entity as select from association composition of to parent on key cast case when then else end
abstract annotate with managed implementation in class unique strict behavior for alias persistent table lock master
dependent by authorization global field readonly mandatory create update delete features instance internal static
action parameter determination modify validation save mapping service expose additional""".split()

glossary = {
    "%cid": "Content ID: a handle for an instance created in this request, before it has a key.",
    "%cid_ref": "Points at a %cid, so a child created by association attaches to a parent created in the same statement.",
    "%tky": "Transactional key: the key fields plus %is_draft when the BO has draft. The safe key to pass around.",
    "%key": "The plain key fields of an instance.",
    "%param": "The action's parameter, typed by the abstract entity.",
    "%msg": "The message object of a reported entry.",
    "%field": "Per-field answer in feature control: read_only, unrestricted, mandatory.",
    "%target": "The child instances of a create by association.",
    "%control": "Flags saying which fields a request actually sets. Field triggers react to these, not to values.",
    "failed": "Instances an operation rejected. A failed entry in a validation stops the whole save.",
    "reported": "Messages for the caller, tied to an instance by key or %cid.",
    "local": "IN LOCAL MODE: EML from inside the BO. Skips feature control and authorization checks; required for internal operations.",
    "internal": "Usable only by the BO's own EML, not exposed to consumers.",
    "strict": "Stricter BDEF syntax check level. strict ( 2 ) is current.",
    "unique": "Each handler method is implemented once in the behavior pool.",
    "determination": "Logic that sets values on modify or on save, triggered by fields or operations.",
    "validation": "A check on save. A failed entry rejects the whole save.",
    "features": "Feature control: what is enabled or read-only, statically or per instance.",
    "static": "An action or function without an instance key, called on the entity set.",
    "abstract": "An abstract entity types parameters or results. No SQL view behind it.",
    "composition": "The child is part of the BO: same lock, authorization and save.",
    "persistent": "persistent table: where the managed runtime writes.",
    "mapping": "CDS element names to table field names, for the managed save.",
    "save_modified": "Saver method for an additional or unmanaged save inside a managed BO.",
    "cleanup_finalize": "Saver method called when the save is rejected in finalize or check_before_save.",
    "new_message_with_text": "Creates a free-text message: no message class, no number.",
    "dependent": "lock / authorization dependent by: the child uses the root's lock and authorization.",
    "master": "lock / authorization / etag master: the entity that owns it for the BO.",
}

drill = [
    ("d01", "ZCRED · save", "ZCRED is `managed with additional save`. What does the framework write, and what does your code write?",
     "The framework writes ZCR_CUSTOMER through the mapping. The code writes the ZCR_CHANGELOG row in `save_modified`. Same LUW, so a failing log insert rolls the customer back too, unlike the old FORM, which committed anyway."),
    ("d02", "ZCRED · EML", "Where did IN LOCAL MODE force extra code in ZCRED?",
     "ChangeCreditLimit updates CreditLimit IN LOCAL MODE, which skips instance feature control. So the action itself forces a priority customer's limit back to the stored value. Without that, read-only would only protect the UI."),
    ("d03", "ZCRED · triggers", "Why does 'Credit limit is unchanged' fire when the value didn't change?",
     "A field trigger reacts to the field being in the modify request (its `%control` flag), not to a different value."),
    ("d04", "Both · save sequence", "The caller invoked an action. Where do the validation's messages come from?",
     "Validations run in the save sequence (check_before_save), not during the action's MODIFY. In stateless OData the save runs in the same request, so the messages come back in the same response."),
    ("d05", "Both · concurrency", "Both BOs are `lock master`. What is still unprotected?",
     "The time between reading the page and pressing Save. The lock lives only for the request, and without `etag master` there is no optimistic check. The old programs took no lock at all."),
    ("d06", "ZMM01 · OData", "Why did ZMM01's Save become a static action instead of a deep insert?",
     "A POST with nested variants was refused: the V4 runtime treats it as an upload and wants virus scan profile /IWBEP/V4/ODATA_UPLOAD active (note 3027559). Activating it was outside the agent's namespace. Draft is the other way out."),
    ("d07", "Both · BDEF", "What does strict ( 2 ) give you, and why isn't ZCRED strict?",
     "Stricter syntax checks: mandatory authorization control, no deprecated syntax, `%tky` as the expected key. ZCRED has no authorization master, which strict mode would reject."),
    ("d08", "Both · messages", "The ports use `new_message_with_text`. What does a consumer lose?",
     "A stable message id. The text matches the old one, but the error shows SABP_BEHV/100 instead of a class and number, so nothing can translate it or key on it. Production code uses a T100 class."),
    ("d09", "ZCRED · design", "Defend or replace the CLASS-DATA side buffer in ZCRED.",
     "It carries the reason, which has no column on the customer. Risks: it is cleared only when a save is rejected, and it is unmanaged state in a managed BO. Replacement: the change log as a composition child, created by association in the action, so the managed save writes it."),
    ("d10", "ZMM01 · fidelity", "ZMM01's validation reports only the first error. Keep it?",
     "For proving parity, yes: the old screen stops at the first E message and the grader compares it. For production, collect all of them so a person fixes three problems in one round trip, and document the difference."),
    ("d11", "ZMM01 · fidelity", "Would you keep SaveTab and ScreenRow in production?",
     "ScreenRow perhaps, as a sort key. SaveTab is dynpro state: drop it, make the defaults unconditional, and get the business to sign off the difference."),
    ("d12", "Proof · limits", "What can't a comparison of rows and messages see?",
     "Authorization, concurrency, success messages, what a person sees (cursor, tabs, value help, the listbox mismatch), and paths no case reaches, like changing an existing ZMM01 article."),
    ("d13", "ZMM01 · old code", "Why can message e05 never appear in the old ZMM01?",
     "sy-subrc is set to 0 by hand before INSERT FROM TABLE, and a duplicate key dumps with SAPSQL_ARRAY_INSERT_DUPREC instead of returning 4. The rollback branch is dead."),
    ("d14", "Both · determinations", "Determination on modify or on save: which, and when?",
     "On modify when the value must exist right away, for the UI or for later logic in the same request. On save for values only needed at commit, like admin stamps or numbers. On-save determinations run before validations."),
    ("d15", "Both · production", "What is missing before either port goes near production?",
     "DCL roles and a real authorization check, an ETag field, T100 messages, a projection layer over the BO, value helps, and probably draft."),
    ("d16", "Proof · method", "Where do the business rules live, and what is the driver allowed to know?",
     "Rules live in the BO. The driver knows only screen mechanics: which field maps to which property, which function code saves, field widths and number notation. Every rule comes back from the service as a message."),
]


def find_line(lines, needle, nth, fid):
    hits = [i + 1 for i, l in enumerate(lines) if needle.rstrip("\n") in l]
    if not hits:
        sys.exit(f"NOT FOUND in {fid}: {needle!r}")
    if nth == 0:
        nth = 1
    if len(hits) > 1 and nth == 1:
        print(f"  note: {len(hits)} hits in {fid} for {needle!r}, using the first (line {hits[0]})")
    return hits[nth - 1]


def build_subject(sid, short, blurb, facts, files, notes, rules, chain, chain_hint, start):
    fs = []
    by = {}
    for f in files:
        lines = load(f["path"])
        name = os.path.basename(f["path"])
        rec = dict(id=f["id"], name=name, short=name.split(".")[0], group=f["group"], adt=f["adt"], role=f["role"],
                   lang=lang_of(name), lines=lines)
        fs.append(rec)
        by[f["id"]] = rec
    ns = []
    for i, (fid, needle, nth, span, tag, title, body) in enumerate(notes):
        ln = find_line(by[fid]["lines"], needle, nth, fid)
        ns.append(dict(id=f"{sid}-n{i}", file=fid, line=ln, span=span, tag=tag, title=title, body=body))
    rs = []
    for title, old, new, note in rules:
        o = dict(file=old[0], line=find_line(by[old[0]]["lines"], old[1], old[2], old[0]), span=old[3])
        n = dict(file=new[0], line=find_line(by[new[0]]["lines"], new[1], new[2], new[0]), span=new[3])
        rs.append(dict(title=title, old=o, new=n, note=note))
    return dict(id=sid, short=short, blurb=blurb, facts=facts, files=fs, notes=ns, rules=rs,
                chain=chain, chainHint=chain_hint, start=start)


cr_chain = [
    dict(type="TABL", name="ZCR_CUSTOMER", sub="+ ZCR_CHANGELOG, ZCR_LIMIT_RULE", file=None,
         info="Untouched by the port. `ZCR_CUSTOMER`: KUNNR, NAME1, WAERS, CREDIT_LIMIT, BLOCKED, PRIORITY. `ZCR_CHANGELOG`: KUNNR, CHANGED_AT, WAERS, OLD_LIMIT, NEW_LIMIT, UNAME, REASON. `ZCR_LIMIT_RULE`: WAERS, THRESHOLD. All fields built-in typed, no data elements."),
    dict(type="DDLS", name="ZPP_CR_C_CUSTOMER", sub="root view entity", file="ZPP_CR_C_CUSTOMER.ddls",
         info="The BO root. ChangeLog and LimitRule are separate view entities; the abstract entities ZPP_CR_A_SELECT and ZPP_CR_A_CHANGE type the action parameters."),
    dict(type="BDEF", name="ZPP_CR_C_CUSTOMER", sub="managed + additional save", file="ZPP_CR_C_CUSTOMER.bdef",
         info="Same name as the root entity, as every BDEF must have."),
    dict(type="CLAS", name="ZPP_CR_BP_CUSTOMER", sub="behavior pool", file="ZPP_CR_BP_CUSTOMER.locals",
         info="Global class with the side buffer; handler and saver in the local types."),
    dict(type="DDLX", name="ZPP_CR_C_CUSTOMER", sub="UI annotations", file="ZPP_CR_C_CUSTOMER.ddlx", info=""),
    dict(type="SRVD", name="ZPP_CR_UI_CREDIT", sub="3 entities", file="ZPP_CR_UI_CREDIT.srvd", info=""),
    dict(type="SRVB", name="ZPP_CR_UI_CREDIT_O4", sub="OData V4 · UI", file=None,
         info="Published at `/sap/opu/odata4/sap/zpp_cr_ui_credit_o4/srvd/sap/zpp_cr_ui_credit/0001/`. A UI binding gives the Fiori Elements preview; a Web API binding would serve the same service without UI annotations."),
    dict(type="APP", name="Fiori Elements", sub="list report + object page", file=None,
         info="No UI5 code was written. The list report and object page are generated from the annotations; the two actions are buttons."),
]
mm_chain = [
    dict(type="TABL", name="ZRET_T_ARTICLE", sub="+ ZRET_T_ART_VAR", file=None,
         info="Untouched by the port. Header: ARTICLE_ID, ARTICLE_NAME, ARTICLE_TYPE, BASE_UOM, ACTIVE_FLAG, PRICE, CURRENCY, GENERIC_ARTICLE_ID, EAN, COLOR, ART_SIZE, CREATED_BY/ON, CHANGED_BY/ON. Variant: ARTICLE_ID, VARIANT_ID, COLOR, SIZE_CODE, EAN, PRICE, CURRENCY."),
    dict(type="DDLS", name="ZPP_MM_R_ARTICLE", sub="root + composition", file="ZPP_MM_R_ARTICLE.ddls",
         info="Root over the header, composition of ZPP_MM_R_VARIANT. The abstract entity ZPP_MM_P_SAVE types the Save action."),
    dict(type="DDLS", name="ZPP_MM_R_VARIANT", sub="child entity", file="ZPP_MM_R_VARIANT.ddls", info=""),
    dict(type="BDEF", name="ZPP_MM_R_ARTICLE", sub="managed, strict ( 2 )", file="ZPP_MM_R_ARTICLE.bdef",
         info="Two entities in one BDEF: Article as lock and authorization master, Variant dependent by _Article."),
    dict(type="CLAS", name="ZPP_MM_BP_ARTICLE", sub="behavior pool", file="ZPP_MM_BP_ARTICLE.locals", info=""),
    dict(type="DDLX", name="ZPP_MM_X_ARTICLE", sub="+ ZPP_MM_X_VARIANT", file="ZPP_MM_X_ARTICLE.ddlx", info=""),
    dict(type="SRVD", name="ZPP_MM_UI_ARTICLE", sub="2 entities", file="ZPP_MM_UI_ARTICLE.srvd", info=""),
    dict(type="SRVB", name="ZPP_MM_UI_ARTICLE_O4", sub="OData V4 · UI", file=None,
         info="Published at `/sap/opu/odata4/sap/zpp_mm_ui_article_o4/srvd/sap/zpp_mm_ui_article/0001/`."),
    dict(type="APP", name="Fiori Elements", sub="list report + object page", file=None,
         info="The three tabs of screen 0200 became three sections of one object page. The object page's own Save would hit the deep insert refusal; the driver uses pressSave."),
]

data = dict(
    kw=dict(abap=kw_abap, cds=kw_cds),
    glossary=glossary,
    drill=[dict(id=i, about=a, q=q, a=ans) for i, a, q, ans in drill],
    subjects=dict(
        ZCRED=build_subject(
            "ZCRED", "credit limit, 1 entity",
            "Change a customer's credit limit with a reason above a per-currency threshold, and log every change. Two screens became two actions on one managed entity; the change log is written by an additional save.",
            [dict(k="Sealed cases, same as the old transaction", v="139 / 140"),
             dict(k="Agent's own cases", v="80 / 80"),
             dict(k="RAP objects", v="10"),
             dict(k="Old program", v="SAPMZCRED, 159 lines")],
            cr_files, cr_notes, cr_rules, cr_chain,
            "Click an object to open it. The tables and the binding have no source here.",
            "ZPP_CR_C_CUSTOMER.bdef"),
        ZMM01=build_subject(
            "ZMM01", "article + variants, parent/child",
            "Article maintenance with a tabstrip and a variant table control, from Romain Hecquet's MIT-licensed retail sandbox (French texts). Parent and child in one managed, strict BDEF; Save is one static action because the deep insert was refused.",
            [dict(k="Sealed cases, same as the old transaction", v="139 / 141"),
             dict(k="Agent's own cases", v="117 / 117"),
             dict(k="RAP objects", v="9"),
             dict(k="Old program", v="SAPMZRET_ART, 5 includes, 291 lines")],
            mm_files, mm_notes, mm_rules, mm_chain,
            "Click an object to open it. The tables and the binding have no source here.",
            "ZPP_MM_R_ARTICLE.bdef"),
    ),
)

blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
for bad in ("\u2014", "\u2013"):  # em and en dash
    if bad in blob:
        sys.exit("dash found in page text")
with open(os.path.join(HERE, "template.html"), encoding="utf-8") as fh:
    tpl = fh.read()
out = tpl.replace("__DATA__", blob)
with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as fh:
    fh.write(out)
print("notes:", {k: len(v["notes"]) for k, v in data["subjects"].items()},
      "rules:", {k: len(v["rules"]) for k, v in data["subjects"].items()}, "bytes:", len(out))
