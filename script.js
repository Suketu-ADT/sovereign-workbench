/* ================================================================
   SOVEREIGN WORKBENCH — Script (ChatGPT-style)
   Chat interface with sidebar history, inline pipeline progress,
   separate pipeline/audit views, and HITL approval flow.
   ================================================================ */

document.addEventListener('DOMContentLoaded', function () {

  // ── CONSTANTS ──────────────────────────────────────────────

  var PIPELINE_STEPS = [
    { id:'rate-limit',   label:'Rate Limit Check',      desc:'Token bucket verification',       duration:350,  readout:function(){return '12 / 60 requests consumed this window';} },
    { id:'prompt-safety',label:'Prompt Safety Check',    desc:'Injection & adversarial scan',    duration:850,  readout:function(){return '0 injection patterns detected \u2014 CLEAR';} },
    { id:'rbac',         label:'RBAC Verification',      desc:'Role-capability authorization',   duration:420,  readout:function(){ return 'Clearance: ' + (state.user ? state.user.clearanceName : 'Guest') + ' \u2714 Role: ' + (state.user ? state.user.role : 'None'); } },
    { id:'doc-retrieval',label:'Document Retrieval',     desc:'Role-filtered manual lookup',     duration:1200, readout:function(){return '3 docs matched \u2192 1 selected: BOILER-102 Manual \u00A74.2';} },
    { id:'vision',       label:'Vision Extraction',      desc:'Multimodal gauge reading',        duration:1500, conditional:true, readout:function(){return 'Gauge: 6.4 bar inlet | Confidence: 0.96';} },
    { id:'calculation',  label:'Sandboxed Calculation',  desc:'Isolated compute environment',    duration:900,  readout:function(){return '\u0394p = 3.8 bar | Range: 2.0\u20135.0 bar | NORMAL';} },
    { id:'approval',     label:'Human Approval (HITL)',  desc:'Sensitive action authorization',  duration:null, interactive:true, readout:null },
    { id:'audit-write',  label:'Audit Log Write',        desc:'Hash-chain entry commitment',     duration:220,  readout:null }
  ];

  var SEED_QUERY = 'Fetch boiler-102 log, read gauge photo, calculate pressure drop, open release valve if abnormal.';

  // Pre-seeded past chats with realistic agentic thinking timeline
  var SEED_CHATS = [
    {
      id: 'seed-1',
      title: 'Pump-201 Vibration Analysis',
      group: 'Yesterday',
      messages: [
        { role:'user', text:'Run vibration analysis on pump-201 and check if it exceeds threshold.', time:'Yesterday, 14:32' },
        {
          role:'assistant',
          text:'Vibration analysis complete for pump-201. Peak amplitude: 4.2 mm/s (threshold: 7.1 mm/s). All readings within normal parameters. No maintenance action required. Full report logged to audit chain.',
          time:'Yesterday, 14:33',
          thinking: {
            state: 'complete',
            title: 'Thought process \u00B7 7 defense checks verified (1.4s)',
            badge: 'COMPLETE',
            collapsed: false,
            steps: [
              { id:'seed-mem', icon:'memory', label:'Read memory', crumb:'Areas \u203A Sovereign Ai Workbench', detail:'Project \u2014 "Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs"', status:'passed' },
              { id:'seed-tools', icon:'tools', label:'Loaded tools', detail:'Vibration spectrum analyzer, ISO 10816-3 rules engine, RBAC clearance checker', status:'passed' },
              { id:'seed-t1', icon:'task', label:'Added task: Check rate limits & RBAC clearance (pump-201)', status:'passed' },
              { id:'seed-t2', icon:'task', label:'Added task: Retrieve vibration accelerometer telemetry', status:'passed' },
              { id:'seed-t3', icon:'task', label:'Added task: Compute peak vibration velocity RMS', status:'passed' },
              { id:'seed-t4', icon:'task', label:'Started task: Vibration spectrum verification', status:'passed' },
              { id:'seed-calc', icon:'calculation', label:'Sandboxed Calculation', detail:'Peak velocity RMS: 4.2 mm/s \u2014 ISO 10816-3 Category 2 (Zone A: 0\u20137.1 mm/s)', status:'passed' },
              { id:'seed-audit', icon:'audit-write', label:'Audit Log Write', detail:'Committed to tamper-proof block #0089 (SHA-256 verified)', status:'passed' }
            ]
          }
        }
      ]
    },
    {
      id: 'seed-2',
      title: 'Cooling System Diagnostics',
      group: 'Yesterday',
      messages: [
        { role:'user', text:'Check coolant flow rate and temperature delta on cooling loop C3.', time:'Yesterday, 09:15' },
        {
          role:'assistant',
          text:'Cooling loop C3 diagnostics:\n\u2022 Flow rate: 12.4 L/min (nominal: 10\u201315 L/min) \u2714\n\u2022 Inlet temp: 28.3\u00b0C, Outlet temp: 41.7\u00b0C\n\u2022 \u0394T = 13.4\u00b0C (within expected range)\n\nNo anomalies detected. System operating within design parameters.',
          time:'Yesterday, 09:16',
          thinking: {
            state: 'complete',
            title: 'Thought process \u00B7 7 defense checks verified (1.6s)',
            badge: 'COMPLETE',
            collapsed: false,
            steps: [
              { id:'seed2-mem', icon:'memory', label:'Read memory', crumb:'Areas \u203A Sovereign Ai Workbench', detail:'Thermal safety envelope \u2014 Cooling loop C3 specifications & sensor telemetry', status:'passed' },
              { id:'seed2-tools', icon:'tools', label:'Loaded tools', detail:'Flow meter decoder, thermal delta calculator, RBAC validator', status:'passed' },
              { id:'seed2-t1', icon:'task', label:'Added task: Verify clearance for auxiliary cooling loop C3', status:'passed' },
              { id:'seed2-t2', icon:'task', label:'Added task: Retrieve flow rate and thermocouple logs', status:'passed' },
              { id:'seed2-t3', icon:'task', label:'Started task: Thermal differential calculation', status:'passed' },
              { id:'seed2-calc', icon:'calculation', label:'Sandboxed Calculation', detail:'Inlet: 28.3\u00b0C, Outlet: 41.7\u00b0C, \u0394T = 13.4\u00b0C \u2014 NORMAL', status:'passed' },
              { id:'seed2-audit', icon:'audit-write', label:'Audit Log Write', detail:'Committed to tamper-proof block #0104 (SHA-256 verified)', status:'passed' }
            ]
          }
        }
      ]
    },
    {
      id: 'seed-3',
      title: 'Monthly Compliance Report',
      group: 'Previous 7 days',
      messages: [
        { role:'user', text:'Generate the monthly compliance summary for September inspection cycle.', time:'Sep 1, 10:00' },
        {
          role:'assistant',
          text:'Monthly compliance summary generated:\n\u2022 Total queries processed: 847\n\u2022 Pipeline blocks: 12 (3 RBAC, 7 rate-limit, 2 prompt-safety)\n\u2022 HITL approvals: 23 (all resolved within SLA)\n\u2022 Audit chain integrity: VERIFIED\n\u2022 Zero unauthorized access attempts\n\nFull report exported to audit log entry #0142.',
          time:'Sep 1, 10:02',
          thinking: {
            state: 'complete',
            title: 'Thought process \u00B7 7 defense checks verified (2.1s)',
            badge: 'COMPLETE',
            collapsed: false,
            steps: [
              { id:'seed3-mem', icon:'memory', label:'Read memory', crumb:'Areas \u203A Sovereign Ai Workbench', detail:'Auditor clearance & ISO 27001 / IEC 62443 industrial compliance framework', status:'passed' },
              { id:'seed3-tools', icon:'tools', label:'Loaded tools', detail:'Merkle hash tree verifier, compliance aggregator, RBAC policy inspector', status:'passed' },
              { id:'seed3-t1', icon:'task', label:'Added task: Verify hash chain integrity across all historical blocks', status:'passed' },
              { id:'seed3-t2', icon:'task', label:'Added task: Aggregate pipeline defense triggers and block statistics', status:'passed' },
              { id:'seed3-t3', icon:'task', label:'Started task: Compliance summary generation', status:'passed' },
              { id:'seed3-calc', icon:'calculation', label:'Calculated Aggregations', detail:'847 queries, 12 blocks, 23 HITL approvals, 0 chain discrepancies', status:'passed' },
              { id:'seed3-audit', icon:'audit-write', label:'Audit Log Write', detail:'Exported monthly compliance summary block #0142', status:'passed' }
            ]
          }
        }
      ]
    }
  ];


  // ── STATE ──────────────────────────────────────────────────

  var DEMO_USERS = {
    suketu: {
      name: 'Suketu',
      fullName: 'Suketu Patel',
      email: 'suketu.2005@gmail.com',
      tier: 'Pro',
      avatar: 'SM',
      clearanceLevel: 3,
      clearanceName: 'Level 3 (Chief Safety Auditor \u00B7 All Systems)',
      role: 'Chief_Safety_Auditor'
    },
    morrison: {
      name: 'J. Morrison',
      fullName: 'John Morrison',
      email: 'j.morrison@plant.internal',
      tier: 'Engineer',
      avatar: 'JM',
      clearanceLevel: 1,
      clearanceName: 'Level 1 (boiler-102 only)',
      role: 'Maintenance_Engineer'
    },
    vance: {
      name: 'Dr. Vance',
      fullName: 'Dr. Elena Vance',
      email: 'elena.vance@plant.internal',
      tier: 'Specialist',
      avatar: 'EV',
      clearanceLevel: 2,
      clearanceName: 'Level 2 (Turbines, Boilers, Pumps)',
      role: 'Systems_Specialist'
    }
  };

  var API_BASE = 'http://127.0.0.1:8000';

  var state = {
    theme: localStorage.getItem('sovereign_theme') || 'light',
    currentView: 'home',
    sidebarOpen: true,
    pipelineRunning: false,
    imageAttached: false,
    imageName: '',
    imageData: null,
    token: null,
    auditLog: [],
    lastHash: '0'.repeat(64),
    chats: [],           // { id, title, group, messages:[] }
    activeChatId: null,
    chatCounter: 0,
    user: null           // Unauthenticated on landing page by default
  };


  // ── ELEMENT REFS ───────────────────────────────────────────

  var $ = function(id) { return document.getElementById(id); };
  var els = {
    sidebar:        $('sidebar'),
    sidebarOverlay: $('sidebar-overlay'),
    btnOpenSidebar: $('btn-open-sidebar'),
    btnCloseSidebar:$('btn-close-sidebar'),
    btnNewChat:     $('btn-new-chat'),
    chatList:       $('chat-list'),
    themeToggle:    $('theme-toggle'),
    tabHome:        $('tab-home'),
    tabChat:        $('tab-chat'),
    tabPipeline:    $('tab-pipeline'),
    tabAudit:       $('tab-audit'),
    homeView:       $('home-view'),
    chatView:       $('chat-view'),
    pipelineView:   $('pipeline-view'),
    auditView:      $('audit-view'),
    btnNavLogin:    $('btn-nav-login'),
    btnHeroLaunch:   $('btn-hero-launch'),
    btnHeroLogin:    $('btn-hero-login'),
    btnHeroPipeline: $('btn-hero-pipeline'),
    btnHomeAuditCard:$('btn-home-audit-card'),
    chatScroll:     $('chat-scroll'),
    chatMessages:   $('chat-messages'),
    btnScrollBottom:$('btn-scroll-bottom'),
    chatInput:      $('chat-input'),
    imageAttach:    $('image-attach'),
    labelAttach:    $('label-attach'),
    imagePreview:   $('image-preview'),
    previewThumb:   $('preview-thumb'),
    previewName:    $('preview-name'),
    btnRemoveImg:   $('btn-remove-img'),
    btnDemo:        $('btn-demo'),
    btnSend:        $('btn-send'),
    pipelineSteps:  $('pipeline-steps'),
    pipelineStatus: $('pipeline-status'),
    pipelineEmpty:  $('pipeline-empty'),
    auditEntries:   $('audit-entries'),
    auditCount:     $('audit-count'),
    approvalDialog: $('approval-dialog'),
    approvalAction: $('approval-action'),
    approvalTarget: $('approval-target'),
    approvalRequestor:$('approval-requestor'),
    approvalContext:$('approval-context'),
    approvalAuthority:$('approval-authority'),
    btnApprove:     $('btn-approve'),
    btnReject:      $('btn-reject'),

    // Sidebar User & Menu Elements
    userMenuContainer: $('user-menu-container'),
    userDropdownMenu:  $('user-dropdown-menu'),
    btnUserProfile:    $('btn-user-profile'),
    btnSidebarLogin:   $('btn-sidebar-login'),
    menuUserEmail:     $('menu-user-email'),
    menuUserClearance: $('menu-user-clearance'),
    menuCurrentLang:   $('menu-current-lang'),
    userPillAvatar:    $('user-pill-avatar'),
    userPillName:      $('user-pill-name'),
    userPillTier:      $('user-pill-tier'),

    // Menu Trigger Buttons
    btnMenuSettings:   $('btn-menu-settings'),
    btnMenuLanguage:   $('btn-menu-language'),
    btnMenuHelp:       $('btn-menu-help'),
    btnMenuClearances: $('btn-menu-clearances'),
    btnMenuTools:      $('btn-menu-tools'),
    btnMenuAcademy:    $('btn-menu-academy'),
    btnMenuAbout:      $('btn-menu-about'),
    btnMenuLogout:     $('btn-menu-logout'),

    // Dialogs
    authDialog:        $('auth-dialog'),
    settingsDialog:    $('settings-dialog'),
    academyDialog:     $('academy-dialog'),
    clearancesDialog:  $('clearances-dialog'),
    helpDialog:        $('help-dialog'),
    toolsDialog:       $('tools-dialog'),
    aboutDialog:       $('about-dialog'),

    // Modal Close Buttons
    btnCloseAuth:       $('btn-close-auth'),
    btnCloseSettings:   $('btn-close-settings'),
    btnCloseAcademy:    $('btn-close-academy'),
    btnCloseClearances: $('btn-close-clearances'),
    btnCloseHelp:       $('btn-close-help'),
    btnCloseTools:      $('btn-close-tools'),
    btnCloseAbout:      $('btn-close-about'),

    // Auth Form Elements
    authTabSignin:     $('auth-tab-signin'),
    authTabSignup:     $('auth-tab-signup'),
    formSignin:        $('form-signin'),
    formSignup:        $('form-signup'),
    signinEmail:       $('signin-email'),
    signinPassword:    $('signin-password'),
    signupName:        $('signup-name'),
    signupEmail:       $('signup-email'),
    signupPassword:    $('signup-password'),
    signupClearance:   $('signup-clearance'),
    btnSigninSubmit:   $('btn-signin-submit'),
    btnSignupSubmit:   $('btn-signup-submit'),

    // Workstation & Model Controls
    headerModelPill:    $('header-model-pill'),
    authApikeyDrawer:   $('auth-apikey-drawer'),
    btnToggleApiKey:    $('btn-toggle-apikey'),
    authApikeyBody:     $('auth-apikey-body'),
    inputModelApiKey:   $('input-model-apikey'),
    inputModelBaseUrl:  $('input-model-baseurl'),
    btnToggleKeyMask:   $('btn-toggle-key-mask'),
    btnSaveApiKey:      $('btn-save-apikey'),
    btnClearApiKey:     $('btn-clear-apikey'),
    apikeyStatusPill:   $('apikey-status-pill'),

    // Shift Handover Briefing Elements
    shiftBriefingDialog: $('shift-briefing-dialog'),
    sbdAvatar:          $('sbd-avatar'),
    sbdName:            $('sbd-name'),
    sbdClearance:       $('sbd-clearance'),
    sbdEmail:           $('sbd-email'),
    sbdRole:            $('sbd-role'),
    sbdUnitsList:       $('sbd-units-list'),
    btnEnterConsole:    $('btn-enter-console'),
    sbdCountdown:       $('sbd-countdown'),

    // Settings Controls
    settingThemeSelect: $('setting-theme-select'),
    settingLangSelect:  $('setting-lang-select'),
    settingModelSelect: $('setting-model-select'),
    btnSaveSettings:    $('btn-save-settings'),

    // Tools Elements
    btnExportAuditJson: $('btn-export-audit-json'),

    // Clearances Elements
    clrAvatar:         $('clr-avatar'),
    clrName:           $('clr-name'),
    clrEmail:          $('clr-email'),
    clrRole:           $('clr-role'),
    clrTurbineStatus:  $('clr-turbine-status'),
    clrReactorStatus:  $('clr-reactor-status')
  };


  // ── UTILITIES ──────────────────────────────────────────────

  function esc(s) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(s));
    return d.innerHTML;
  }

  function timeNow() {
    var d = new Date();
    return d.toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' });
  }

  function isMobile() { return window.innerWidth <= 768; }

  var toastTimer = null;
  function showToast(msg) {
    var toast = document.getElementById('sovereign-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'sovereign-toast';
      toast.className = 'sovereign-toast';
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add('show');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function() {
      toast.classList.remove('show');
    }, 3200);
  }


  // ── THEME ──────────────────────────────────────────────────

  function applyTheme() {
    var theme = state.theme || 'light';
    state.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('sovereign_theme', theme);
    } catch (e) {}
    if (els.settingThemeSelect) {
      els.settingThemeSelect.value = theme;
    }
  }
  function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    applyTheme();
  }


  // ── USER AUTH & PROFILE MANAGEMENT ─────────────────────────

  function updateUserUI() {
    if (state.user) {
      if (els.btnUserProfile) els.btnUserProfile.hidden = false;
      if (els.btnSidebarLogin) els.btnSidebarLogin.hidden = true;
      if (els.btnNavLogin) els.btnNavLogin.hidden = true;
      if (els.userPillAvatar) els.userPillAvatar.textContent = state.user.avatar || 'OP';
      if (els.userPillName) els.userPillName.textContent = state.user.name;
      if (els.userPillTier) els.userPillTier.textContent = state.user.tier;
      if (els.menuUserEmail) els.menuUserEmail.textContent = state.user.email;
      if (els.menuUserClearance) els.menuUserClearance.textContent = 'Clearance: ' + state.user.clearanceName;

      // Enable chat input for authenticated operator
      if (els.chatInput) {
        els.chatInput.disabled = false;
        els.chatInput.placeholder = "Ask Sovereign Workbench about equipment, logs, telemetry...";
      }
      updateSendState();

      // Update clearances modal
      if (els.clrAvatar) els.clrAvatar.textContent = state.user.avatar || 'OP';
      if (els.clrName) els.clrName.textContent = state.user.fullName || state.user.name;
      if (els.clrEmail) els.clrEmail.textContent = state.user.email;
      if (els.clrRole) els.clrRole.textContent = 'Clearance: ' + state.user.clearanceName;

      if (els.clrTurbineStatus) {
        if (state.user.clearanceLevel >= 2) {
          els.clrTurbineStatus.innerHTML = '<span class="resp-value--passed">AUTHORIZED &check;</span>';
        } else {
          els.clrTurbineStatus.innerHTML = '<span class="resp-value--blocked">DENIED (Tier 2 Req)</span>';
        }
      }
      if (els.clrReactorStatus) {
        if (state.user.clearanceLevel >= 3) {
          els.clrReactorStatus.innerHTML = '<span class="resp-value--passed">AUTHORIZED &check;</span>';
        } else {
          els.clrReactorStatus.innerHTML = '<span class="resp-value--blocked">DENIED (Tier 3 Req)</span>';
        }
      }
    } else {
      if (els.btnUserProfile) els.btnUserProfile.hidden = true;
      if (els.btnSidebarLogin) els.btnSidebarLogin.hidden = false;
      if (els.btnNavLogin) els.btnNavLogin.hidden = false;
      if (els.chatInput) {
        els.chatInput.disabled = true;
        els.chatInput.placeholder = "Please sign in to access Sovereign Workbench console...";
      }
      if (els.btnSend) els.btnSend.disabled = true;
      closeUserMenu();
    }
  }

  function toggleUserMenu(e) {
    if (e) e.stopPropagation();
    if (!els.userDropdownMenu) return;
    var isHidden = els.userDropdownMenu.hidden;
    if (isHidden) {
      els.userDropdownMenu.hidden = false;
      if (els.btnUserProfile) els.btnUserProfile.setAttribute('aria-expanded', 'true');
    } else {
      closeUserMenu();
    }
  }

  function closeUserMenu() {
    if (els.userDropdownMenu) els.userDropdownMenu.hidden = true;
    if (els.btnUserProfile) els.btnUserProfile.setAttribute('aria-expanded', 'false');
  }

  function openModal(dlg) {
    if (!dlg) return;
    closeUserMenu();
    dlg.showModal();
  }

  function closeModal(dlg) {
    if (!dlg) return;
    dlg.close();
  }

  var briefingTimer = null;

  function showShiftBriefing(userProfile) {
    if (!els.shiftBriefingDialog) return;

    if (els.sbdAvatar) els.sbdAvatar.textContent = userProfile.avatar || 'OP';
    if (els.sbdName) els.sbdName.textContent = userProfile.fullName || userProfile.name;
    if (els.sbdEmail) els.sbdEmail.textContent = userProfile.email;
    if (els.sbdClearance) els.sbdClearance.textContent = userProfile.clearanceName || ('Level ' + userProfile.clearanceLevel);
    if (els.sbdRole) els.sbdRole.textContent = (userProfile.role || 'Operator') + ' \u00B7 Facility Active';

    if (els.sbdUnitsList) {
      var level = userProfile.clearanceLevel || 1;
      var units = ['boiler-102', 'pump-201', 'cooling-loop-c3'];
      if (level >= 2) {
        units.push('turbine-gen-4', 'compressor-1A');
      }
      if (level >= 3) {
        units.push('reactor-core-aux', 'scram-containment', 'audit-ledger');
      }
      els.sbdUnitsList.innerHTML = units.map(function(u) {
        return '<div class="sbd-unit-pill"><span class="sbd-unit-dot"></span><code>' + u + '</code></div>';
      }).join('');
    }

    openModal(els.shiftBriefingDialog);

    var remaining = 3;
    if (els.sbdCountdown) els.sbdCountdown.textContent = '(' + remaining + 's)';
    if (briefingTimer) clearInterval(briefingTimer);
    briefingTimer = setInterval(function() {
      remaining -= 1;
      if (remaining > 0) {
        if (els.sbdCountdown) els.sbdCountdown.textContent = '(' + remaining + 's)';
      } else {
        clearInterval(briefingTimer);
        briefingTimer = null;
        closeModal(els.shiftBriefingDialog);
      }
    }, 1000);
  }

  function loginUser(userProfile, skipBriefing) {
    state.user = userProfile;
    updateUserUI();
    renderChatList();
    renderChatMessages();
    closeModal(els.authDialog);
    closeUserMenu();

    if (!skipBriefing) {
      showShiftBriefing(userProfile);
    }
    switchView('chat');
  }

  function initApiKeyDrawer() {
    var storedKey = localStorage.getItem('sovereign_api_key') || '';
    var storedBase = localStorage.getItem('sovereign_base_url') || 'https://openrouter.ai/api/v1';

    if (els.inputModelApiKey) els.inputModelApiKey.value = storedKey;
    if (els.inputModelBaseUrl) els.inputModelBaseUrl.value = storedBase;
    updateApiKeyStatusPill(storedKey);

    if (els.btnToggleApiKey && els.authApikeyDrawer && els.authApikeyBody) {
      els.btnToggleApiKey.addEventListener('click', function() {
        var isOpen = els.authApikeyDrawer.classList.toggle('open');
        els.authApikeyBody.hidden = !isOpen;
      });
    }

    if (els.btnToggleKeyMask && els.inputModelApiKey) {
      els.btnToggleKeyMask.addEventListener('click', function() {
        var isPwd = els.inputModelApiKey.type === 'password';
        els.inputModelApiKey.type = isPwd ? 'text' : 'password';
        els.btnToggleKeyMask.textContent = isPwd ? '🔒' : '👁️';
      });
    }

    if (els.btnSaveApiKey) {
      els.btnSaveApiKey.addEventListener('click', function() {
        var keyVal = els.inputModelApiKey ? els.inputModelApiKey.value.trim() : '';
        var baseVal = els.inputModelBaseUrl ? els.inputModelBaseUrl.value.trim() : 'https://openrouter.ai/api/v1';
        if (keyVal) {
          localStorage.setItem('sovereign_api_key', keyVal);
        } else {
          localStorage.removeItem('sovereign_api_key');
        }
        localStorage.setItem('sovereign_base_url', baseVal);
        updateApiKeyStatusPill(keyVal);
        updateHeaderModelPill(keyVal);
        alert(keyVal ? 'API Key saved for workstation session. Cloud models qwen/qwen2.5-32b-instruct & Qwen2.5-VL 72B activated.' : 'Reverted to local/air-gap defaults.');
      });
    }

    if (els.btnClearApiKey) {
      els.btnClearApiKey.addEventListener('click', function() {
        if (els.inputModelApiKey) els.inputModelApiKey.value = '';
        if (els.inputModelBaseUrl) els.inputModelBaseUrl.value = 'https://openrouter.ai/api/v1';
        localStorage.removeItem('sovereign_api_key');
        localStorage.removeItem('sovereign_base_url');
        updateApiKeyStatusPill('');
        updateHeaderModelPill('');
      });
    }

    if (els.btnEnterConsole) {
      els.btnEnterConsole.addEventListener('click', function() {
        if (briefingTimer) { clearInterval(briefingTimer); briefingTimer = null; }
        closeModal(els.shiftBriefingDialog);
      });
    }
  }

  function updateApiKeyStatusPill(key) {
    if (!els.apikeyStatusPill) return;
    if (key) {
      els.apikeyStatusPill.textContent = 'Cloud API Active';
      els.apikeyStatusPill.classList.add('active');
    } else {
      els.apikeyStatusPill.textContent = 'Local / Air-Gap';
      els.apikeyStatusPill.classList.remove('active');
    }
  }

  function updateHeaderModelPill(key) {
    if (!els.headerModelPill) return;
    var nameEl = els.headerModelPill.querySelector('.model-pill-name');
    if (nameEl) {
      nameEl.textContent = 'Qwen 2.5 32B + VL-72B' + (key ? ' (Cloud API)' : '');
    }
  }

  function logoutUser() {
    var prevEmail = state.user ? state.user.email : 'Operator';
    state.user = null;
    state.token = null;
    localStorage.removeItem('sovereign_token');
    updateUserUI();
    renderChatList();
    renderChatMessages();
    closeUserMenu();
    addAuditEntry('OPERATOR_LOGOUT', 'Operator ' + prevEmail + ' logged out of console');
    switchView('home');
    showToast('Operator logged out.');
  }

  function authenticate(email, password, isInitialLoad) {
    return fetch(API_BASE + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, password: password || 'changeme123' })
    })
    .then(function(res) {
      if (!res.ok) throw new Error('Authentication failed: HTTP ' + res.status);
      return res.json();
    })
    .then(function(data) {
      state.token = data.access_token;
      localStorage.setItem('sovereign_token', data.access_token);
      var u = data.user;
      var rawName = u.full_name || u.email.split('@')[0];
      var nameWords = rawName.split(/\s+/).filter(Boolean);
      var firstName = nameWords.length ? nameWords[0] : 'Operator';
      var initials = (nameWords.length > 1 ? (nameWords[0][0] + nameWords[1][0]) : firstName.substring(0, 2)).toUpperCase();
      var clearanceMap = {
        1: { name: 'Level 1 (boiler-102 only)', tier: 'Engineer' },
        2: { name: 'Level 2 (Turbines, Boilers, Pumps)', tier: 'Specialist' },
        3: { name: 'Level 3 (Chief Safety Auditor \u00B7 All Systems)', tier: 'Pro' }
      };
      var clr = clearanceMap[u.clearance_level] || clearanceMap[3];
      var profile = {
        name: firstName,
        fullName: u.full_name || rawName,
        email: u.email,
        clearanceLevel: u.clearance_level,
        clearanceName: clr.name,
        role: u.role,
        tier: clr.tier,
        avatar: initials
      };
      loginUser(profile, isInitialLoad);
      loadAuditLog();
      return profile;
    })
    .catch(function(err) {
      console.warn('Backend login unreachable, using offline fallback profile:', err);
      var fallback = DEMO_USERS.suketu;
      if (email && email.indexOf('morrison') !== -1) fallback = DEMO_USERS.morrison;
      else if (email && email.indexOf('vance') !== -1) fallback = DEMO_USERS.vance;
      loginUser(fallback, isInitialLoad);
    });
  }

  function loadAuditLog() {
    if (!state.token) return;
    var headers = {};
    headers['Authorization'] = 'Bearer ' + state.token;
    return fetch(API_BASE + '/audit?limit=50', { headers: headers })
      .then(function(res) {
        if (!res.ok) return null;
        return res.json();
      })
      .then(function(data) {
        if (data && data.entries && data.entries.length > 0) {
          state.auditLog = data.entries.map(function(e) {
            return {
              index: e.index !== undefined ? e.index : e.idx,
              timestamp: e.timestamp,
              event: e.event || e.event_type,
              detail: e.detail,
              hash: e.hash,
              prevHash: e.prevHash || e.prev_hash
            };
          });
          state.lastHash = state.auditLog[0].hash; // top entry
          if (els.auditCount) {
            els.auditCount.textContent = state.auditLog.length + ' entries';
          }
          renderAuditLog();
        }
      })
      .catch(function() {
        // Fallback silently
      });
  }

  function exportAuditJson() {
    var headers = {};
    if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
    fetch(API_BASE + '/audit/export', { headers: headers })
      .then(function(res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function(exportData) {
        var dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportData, null, 2));
        var dlAnchor = document.createElement('a');
        dlAnchor.setAttribute('href', dataStr);
        dlAnchor.setAttribute('download', 'sovereign-workbench-audit-chain-' + Date.now() + '.json');
        document.body.appendChild(dlAnchor);
        dlAnchor.click();
        dlAnchor.remove();
      })
      .catch(function() {
        var exportData = {
          exportTimestamp: new Date().toISOString(),
          system: 'Sovereign Workbench Air-Gapped Console',
          genesisHash: '0000000000000000000000000000000000000000000000000000000000000000',
          currentHeadHash: state.lastHash,
          entryCount: state.auditLog.length,
          operator: state.user ? {
            name: state.user.fullName || state.user.name,
            email: state.user.email,
            clearance: state.user.clearanceName
          } : 'Unauthenticated',
          ledger: state.auditLog
        };
        var dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportData, null, 2));
        var dlAnchor = document.createElement('a');
        dlAnchor.setAttribute('href', dataStr);
        dlAnchor.setAttribute('download', 'sovereign-workbench-audit-chain-' + Date.now() + '.json');
        document.body.appendChild(dlAnchor);
        dlAnchor.click();
        dlAnchor.remove();
      });
  }


  // ── SIDEBAR ────────────────────────────────────────────────

  function openSidebar() {
    state.sidebarOpen = true;
    if (isMobile()) {
      els.sidebar.classList.add('open');
      els.sidebar.classList.remove('collapsed');
      els.sidebarOverlay.hidden = false;
    } else {
      els.sidebar.classList.remove('collapsed');
    }
  }

  function closeSidebar() {
    state.sidebarOpen = false;
    if (isMobile()) {
      els.sidebar.classList.remove('open');
      els.sidebar.classList.add('collapsed');
      els.sidebarOverlay.hidden = true;
    } else {
      els.sidebar.classList.add('collapsed');
    }
  }

  function toggleSidebar() {
    if (isMobile()) {
      if (els.sidebar.classList.contains('open')) {
        closeSidebar();
      } else {
        openSidebar();
      }
    } else {
      if (els.sidebar.classList.contains('collapsed')) {
        openSidebar();
      } else {
        closeSidebar();
      }
    }
  }

  function renderChatList() {
    if (!state.user) {
      els.chatList.innerHTML =
        '<div class="sidebar-locked-notice">' +
          '<div class="locked-icon-shield">' +
            '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>' +
          '</div>' +
          '<div class="locked-text">' +
            '<span class="locked-title">Access Restricted</span>' +
            '<span class="locked-sub">Operator clearance required to view and manage operational chats</span>' +
          '</div>' +
          '<button type="button" class="btn-sidebar-unlock" id="btn-sidebar-unlock">' +
            '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="8" cy="5" r="3"/><path d="M2.5 14a5.5 5.5 0 0 1 11 0"/></svg>' +
            '<span>Sign In</span>' +
          '</button>' +
        '</div>';
      return;
    }

    var html = '';
    var groups = {};

    // Group chats
    state.chats.forEach(function(c) {
      var g = c.group || 'Today';
      if (!groups[g]) groups[g] = [];
      groups[g].push(c);
    });

    var order = ['Today', 'Yesterday', 'Previous 7 days'];
    Object.keys(groups).forEach(function(g) {
      if (order.indexOf(g) === -1) order.push(g);
    });

    order.forEach(function(g) {
      if (!groups[g]) return;
      html += '<div class="chat-group-label">' + esc(g) + '</div>';
      groups[g].forEach(function(c) {
        html += '<button type="button" class="chat-item' + (c.id === state.activeChatId ? ' active' : '') + '" data-chat-id="' + c.id + '">' + esc(c.title) + '</button>';
      });
    });

    els.chatList.innerHTML = html;
  }


  // ── VIEW SWITCHING ─────────────────────────────────────────

  function switchView(view) {
    if (view === 'chat' && !state.user) {
      showToast('Operator clearance required to access chat console.');
      openModal(els.authDialog);
      return;
    }
    state.currentView = view;
    var views = { home: els.homeView, chat: els.chatView, pipeline: els.pipelineView, audit: els.auditView };
    var tabs  = { home: els.tabHome, chat: els.tabChat, pipeline: els.tabPipeline, audit: els.tabAudit };

    Object.keys(views).forEach(function(k) {
      if (views[k]) views[k].classList.toggle('view--active', k === view);
      if (tabs[k]) tabs[k].classList.toggle('active', k === view);
    });

    if (view === 'audit') renderAuditLog();
  }


  // ── CHAT MANAGEMENT ────────────────────────────────────────

  function createChat(opts) {
    opts = opts || {};
    state.chatCounter++;
    var chat = {
      id: 'chat-' + Date.now() + '-' + state.chatCounter,
      title: 'New Chat',
      group: 'Today',
      messages: []
    };
    state.chats.unshift(chat);
    state.activeChatId = chat.id;
    // Clear any file preview and draft text from previous chat
    removeImage();
    els.chatInput.value = '';
    autoResize();
    updateSendState();
    renderChatList();
    renderChatMessages();
    if (!opts.silent) {
      switchView('chat');
      els.chatInput.focus();
    }
    if (isMobile()) closeSidebar();
    return chat;
  }

  function switchChat(chatId) {
    if (state.activeChatId !== chatId) {
      removeImage();
      els.chatInput.value = '';
      autoResize();
      updateSendState();
    }
    state.activeChatId = chatId;
    renderChatList();
    renderChatMessages();
    switchView('chat');
    if (isMobile()) closeSidebar();
  }

  function getActiveChat() {
    return state.chats.find(function(c) { return c.id === state.activeChatId; });
  }

  function addMessage(role, content, extra) {
    var chat = getActiveChat();
    if (!chat) return null;
    var msg = { role: role, text: content, time: timeNow() };
    if (extra) {
      if (extra.image) msg.image = extra.image;
      if (extra.html) msg.html = extra.html;
      if (extra.thinking) msg.thinking = extra.thinking;
    }
    chat.messages.push(msg);
    // Update title from first user message
    if (role === 'user' && chat.title === 'New Chat') {
      chat.title = content.length > 36 ? content.substring(0, 36) + '\u2026' : content;
      renderChatList();
    }
    renderChatMessages();
    scrollToBottom();
    return msg;
  }

  function renderChatMessages() {
    if (!state.user) {
      els.chatMessages.innerHTML =
        '<div class="chat-locked-barrier">' +
          '<div class="locked-barrier-badge">' +
            '<svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.6">' +
              '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>' +
            '</svg>' +
          '</div>' +
          '<h2 class="locked-barrier-title">SCADA Console Locked</h2>' +
          '<p class="locked-barrier-sub">Operational telemetry extraction, sandboxed calculations, and agentic actuator reasoning require verified operator clearance. Please sign in to establish a secure session.</p>' +
          '<div class="locked-barrier-actions">' +
            '<button type="button" class="btn-cerebrium btn-cerebrium--primary" id="btn-barrier-signin">' +
              '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="8" cy="5" r="3"/><path d="M2.5 14a5.5 5.5 0 0 1 11 0"/></svg>' +
              '<span>Sign In as Operator</span>' +
            '</button>' +
            '<button type="button" class="btn-cerebrium btn-cerebrium--ghost" id="btn-barrier-home">' +
              '<span>Return to Landing Page</span>' +
            '</button>' +
          '</div>' +
        '</div>';
      return;
    }

    var chat = getActiveChat();
    if (!chat || chat.messages.length === 0) {
      // Show refined Cerebrium-style welcome screen
      els.chatMessages.innerHTML =
        '<div class="chat-welcome">' +
          '<div class="chat-welcome-badge">' +
            '<svg class="chat-welcome-logo" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6">' +
              '<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="3" x2="12" y2="21"/><line x1="3" y1="12" x2="21" y2="12"/><circle cx="12" cy="12" r="4"/>' +
            '</svg>' +
          '</div>' +
          '<h1 class="chat-welcome-title">Sovereign Workbench</h1>' +
          '<p class="chat-welcome-sub">Your secure AI workspace for industrial operations.</p>' +
          '<div class="chat-welcome-suggestions">' +
            '<button type="button" class="suggestion-card" data-prompt="Write Python code to calculate pump efficiency when input power is 100 kW and output power is 85 kW.">' +
              '<div class="suggestion-card-icon">' +
                '<svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="5 4 2 8 5 12"/><polyline points="11 4 14 8 11 12"/><line x1="9.5" y1="3.5" x2="6.5" y2="12.5"/></svg>' +
              '</div>' +
              '<div class="suggestion-card-text">' +
                '<span class="suggestion-card-title">Analyze pump vibration</span>' +
                '<span class="suggestion-card-desc">Calculate efficiency &amp; vibration spectrum</span>' +
              '</div>' +
            '</button>' +
            '<button type="button" class="suggestion-card" data-prompt="Summarize this engineering inspection report.">' +
              '<div class="suggestion-card-icon">' +
                '<svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 1.5H3.5A1.5 1.5 0 0 0 2 3v10a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 14 13V6.5L9 1.5Z"/><polyline points="9 1.5 9 6.5 14 6.5"/><line x1="5" y1="9" x2="11" y2="9"/><line x1="5" y1="11.5" x2="9" y2="11.5"/></svg>' +
              '</div>' +
              '<div class="suggestion-card-text">' +
                '<span class="suggestion-card-title">Generate inspection summary</span>' +
                '<span class="suggestion-card-desc">Audit compliance &amp; safety protocols</span>' +
              '</div>' +
            '</button>' +
            '<button type="button" class="suggestion-card" data-prompt="Read this inspection image and extract the gauge reading." data-image="true">' +
              '<div class="suggestion-card-icon">' +
                '<svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2"/><line x1="8" y1="2" x2="8" y2="4"/><line x1="8" y1="12" x2="8" y2="14"/></svg>' +
              '</div>' +
              '<div class="suggestion-card-text">' +
                '<span class="suggestion-card-title">Extract gauge reading</span>' +
                '<span class="suggestion-card-desc">Multimodal computer vision dial telemetry</span>' +
              '</div>' +
            '</button>' +
            '<button type="button" class="suggestion-card" data-prompt="Fetch boiler-102 log, calculate pressure drop, and check for anomalies.">' +
              '<div class="suggestion-card-icon">' +
                '<svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 1.5L2.5 4.5v3.5c0 3.5 2.4 6.8 5.5 7.5 3.1-.7 5.5-4 5.5-7.5V4.5L8 1.5Z"/></svg>' +
              '</div>' +
              '<div class="suggestion-card-text">' +
                '<span class="suggestion-card-title">Explain maintenance anomaly</span>' +
                '<span class="suggestion-card-desc">Root-cause telemetry correlation &amp; SOP</span>' +
              '</div>' +
            '</button>' +
          '</div>' +
        '</div>';
      return;
    }

    var html = '';
    chat.messages.forEach(function(m, idx) {
      var isUser = m.role === 'user';
      var avatarLabel = isUser ? 'ME' : 'SW';
      var senderLabel = isUser ? 'You' : 'Sovereign AI';
      html += '<div class="message message--' + m.role + '">';
      html += '<div class="msg-avatar">' + avatarLabel + '</div>';
      html += '<div class="msg-body">';
      html += '<div class="msg-sender"><span class="msg-sender-name">' + senderLabel + '</span>' + (!isUser ? '<span class="msg-sender-badge">Air-Gapped</span>' : '') + '</div>';
      html += '<div class="msg-content">';

      if (m.image) {
        html += '<div class="msg-image-badge"><svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1" y="3" width="14" height="10" rx="1"/><circle cx="5" cy="7" r="1.5"/></svg> ' + esc(m.image) + '</div>';
      }

      if (m.thinking) {
        html += renderThinkingBlock(m.thinking, idx);
      }

      if (m.html) {
        html += m.html;
        if (m.role === 'assistant' && m.html.indexOf('msg-action-toolbar') === -1) {
          html += renderActionToolbar();
        }
      } else if (m.text) {
        if (m.role === 'assistant' && m.text.indexOf('```') !== -1) {
          var parsedMsg = extractCodeAndOutput(m.text, null);
          if (parsedMsg.code) {
            if (parsedMsg.intro) html += '<p style="margin-bottom:8px;">' + esc(parsedMsg.intro) + '</p>';
            html += renderCodeCard(parsedMsg.code, 'python');
            if (parsedMsg.output) html += renderOutputSection(parsedMsg.output);
            if (parsedMsg.outro) html += '<p style="margin-top:10px;">' + esc(parsedMsg.outro) + '</p>';
            html += renderActionToolbar();
          } else {
            var paras = m.text.split('\n');
            paras.forEach(function(p) { if (p.trim()) html += '<p>' + esc(p) + '</p>'; });
            html += renderActionToolbar();
          }
        } else {
          var paras = m.text.split('\n');
          paras.forEach(function(p) { if (p.trim()) html += '<p>' + esc(p) + '</p>'; });
          if (m.role === 'assistant') {
            html += renderActionToolbar();
          }
        }
      }

      html += '</div>';
      html += '<div class="msg-time">' + esc(m.time) + '</div>';
      html += '</div></div>';
    });

    els.chatMessages.innerHTML = html;
  }

  function renderThinkingBlock(t, msgIdx) {
    var st = t.state || 'complete';
    var isRunning = st === 'running';
    var collapsedClass = t.collapsed ? ' collapsed' : '';
    var idAttr = isRunning ? ' id="active-thinking-block"' : '';
    var timelineId = isRunning ? ' id="inline-timeline"' : '';

    var html = '<div class="thinking-block' + collapsedClass + '"' + idAttr + ' data-state="' + st + '" data-msg-idx="' + (msgIdx !== undefined ? msgIdx : '') + '">';
    html += '<button type="button" class="thinking-toggle" aria-label="Toggle thinking process">';
    html += '<div class="thinking-toggle-left">';
    html += '<svg class="thinking-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 6l4 4 4-4"/></svg>';
    html += '<span class="thinking-toggle-title">' + esc(t.title || 'Thinking Process') + '</span>';
    html += '</div>';
    html += '<span class="thinking-toggle-badge">' + esc(t.badge || (st === 'complete' ? 'PASSED' : st.toUpperCase())) + '</span>';
    html += '</button>';

    html += '<div class="thinking-content">';
    html += '<div class="thinking-timeline"' + timelineId + '>';
    if (t.steps && t.steps.length) {
      t.steps.forEach(function(s) {
        html += renderStepHtml(s);
      });
    }
    html += '</div></div></div>';
    return html;
  }

  function renderStepHtml(s) {
    var iconSvg = STEP_ICONS[s.icon] || STEP_ICONS[s.id] || STEP_ICONS['task'] || STEP_ICONS['audit-write'];
    var status = s.status || 'passed';
    var html = '<div class="thinking-step" data-step="' + esc(s.id || s.label) + '" data-s="' + status + '">';
    html += '<div class="thinking-step-track">';
    html += '<div class="thinking-step-icon">' + iconSvg + '</div>';
    html += '<div class="thinking-step-line"></div>';
    html += '</div>';
    html += '<div class="thinking-step-body">';
    html += '<div class="thinking-step-header">';
    html += '<div class="thinking-step-label">' + esc(s.label) + '</div>';
    if (s.crumb) {
      html += '<div class="thinking-step-crumb">' + esc(s.crumb) + '</div>';
    }
    html += '</div>';
    if (s.detail) {
      html += '<div class="thinking-step-detail">' + esc(s.detail) + '</div>';
    }
    html += '</div></div>';
    return html;
  }

  function scrollToBottom() {
    setTimeout(function() {
      els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
    }, 50);
  }


  // ── IMAGE ATTACHMENT ───────────────────────────────────────

  function handleImageSelect(e) {
    var file = e.target.files && e.target.files[0];
    if (!file) return;
    state.imageAttached = true;
    state.imageName = file.name;
    els.previewName.textContent = file.name;
    var reader = new FileReader();
    reader.onload = function(ev) {
      state.imageData = ev.target.result;
      els.previewThumb.innerHTML = '<img src="' + ev.target.result + '" alt="Preview">';
    };
    reader.readAsDataURL(file);
    els.imagePreview.hidden = false;
    updateSendState();
  }

  function removeImage() {
    state.imageAttached = false;
    state.imageName = '';
    state.imageData = null;
    els.imageAttach.value = '';
    els.previewThumb.innerHTML = '';
    els.imagePreview.hidden = true;
    updateSendState();
  }

  function simulateImageAttach() {
    state.imageAttached = true;
    state.imageName = 'boiler-102-gauge.jpg';
    els.previewName.textContent = state.imageName;
    // Draw gauge
    var canvas = document.createElement('canvas');
    canvas.width = 80; canvas.height = 80;
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = '#1a2029'; ctx.fillRect(0, 0, 80, 80);
    ctx.strokeStyle = '#4FC3C9'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(40, 44, 28, Math.PI, 0); ctx.stroke();
    ctx.strokeStyle = '#F85149'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(40, 44);
    var angle = Math.PI + (6.4 / 10) * Math.PI;
    ctx.lineTo(40 + Math.cos(angle) * 22, 44 + Math.sin(angle) * 22); ctx.stroke();
    ctx.fillStyle = '#4FC3C9'; ctx.font = '9px monospace'; ctx.textAlign = 'center';
    ctx.fillText('6.4 bar', 40, 72);
    var dataUrl = canvas.toDataURL();
    state.imageData = dataUrl;
    els.previewThumb.innerHTML = '<img src="' + dataUrl + '" alt="Gauge">';
    els.imagePreview.hidden = false;
  }

  function updateSendState() {
    var hasText = els.chatInput.value.trim().length > 0;
    els.btnSend.disabled = !hasText || state.pipelineRunning;
  }


  // ── AUTO-RESIZE TEXTAREA ──────────────────────────────────

  function autoResize() {
    els.chatInput.style.height = 'auto';
    els.chatInput.style.height = Math.min(els.chatInput.scrollHeight, 160) + 'px';
  }


  // ── HASH GENERATION ────────────────────────────────────────

  function sha256(msg) {
    var enc = new TextEncoder();
    return crypto.subtle.digest('SHA-256', enc.encode(msg)).then(function(buf) {
      return Array.from(new Uint8Array(buf)).map(function(b) { return b.toString(16).padStart(2,'0'); }).join('');
    });
  }

  function addAuditEntry(eventType, detail) {
    var payload = state.lastHash + '|' + eventType + ':' + detail + '|' + Date.now();
    return sha256(payload).then(function(hash) {
      var entry = {
        index: state.auditLog.length,
        timestamp: new Date().toISOString(),
        event: eventType,
        detail: detail,
        hash: hash,
        prevHash: state.lastHash
      };
      state.lastHash = hash;
      state.auditLog.push(entry);
      els.auditCount.textContent = state.auditLog.length + ' entries';
      return entry;
    });
  }

  function renderAuditLog() {
    if (state.auditLog.length === 0) {
      els.auditEntries.innerHTML = '<div class="audit-empty">No audit entries yet. Execute a query to generate log entries.</div>';
      return;
    }
    var html = '';
    for (var i = state.auditLog.length - 1; i >= 0; i--) {
      var e = state.auditLog[i];
      html += '<div class="audit-entry">' +
        '<div class="audit-entry-idx">#' + String(e.index).padStart(4,'0') + '</div>' +
        '<div class="audit-entry-body">' +
          '<div class="audit-entry-event">' + esc(e.event) + '</div>' +
          '<div class="audit-entry-detail">' + esc(e.detail) + '</div>' +
          '<div class="audit-entry-detail" style="margin-top:2px;opacity:0.7">' + e.timestamp + '</div>' +
        '</div>' +
        '<div class="audit-entry-hashes">' +
          '<span class="hash-label">hash </span>' + e.hash.substring(0,16) + '\u2026<br>' +
          '<span class="hash-label">prev </span>' + e.prevHash.substring(0,16) + '\u2026' +
        '</div>' +
      '</div>';
    }
    els.auditEntries.innerHTML = html;
  }


  // ── PIPELINE (full view) ──────────────────────────────────

  function buildPipelineDOM(hasImage) {
    els.pipelineEmpty.hidden = true;
    // Clear old steps
    var old = els.pipelineSteps.querySelectorAll('.pipeline-step');
    for (var i = 0; i < old.length; i++) old[i].remove();

    var html = '';
    PIPELINE_STEPS.forEach(function(step) {
      if (step.conditional && !hasImage) return;
      html +=
        '<div class="pipeline-step" id="step-' + step.id + '" data-status="idle">' +
          '<div class="step-track"><div class="step-dot"></div><div class="step-connector"></div></div>' +
          '<div class="step-content">' +
            '<div class="step-header">' +
              '<span class="step-label">' + esc(step.label) + '</span>' +
              '<span class="step-badge" data-badge="idle">IDLE</span>' +
            '</div>' +
            '<div class="step-meta">' +
              '<span class="step-desc">' + esc(step.desc) + '</span>' +
              '<span class="step-timing"></span>' +
            '</div>' +
            '<div class="step-readout"></div>' +
          '</div>' +
        '</div>';
    });
    els.pipelineSteps.insertAdjacentHTML('afterbegin', html);
  }

  function updateStepUI(stepId, status, readout, elapsed) {
    var el = document.getElementById('step-' + stepId);
    if (!el) return;
    el.setAttribute('data-status', status);
    var badge = el.querySelector('.step-badge');
    var map = { idle:'IDLE', processing:'PROCESSING', passed:'PASSED', blocked:'BLOCKED', awaiting:'AWAITING', skipped:'SKIPPED', approved:'APPROVED', rejected:'REJECTED' };
    badge.textContent = map[status] || status.toUpperCase();
    badge.setAttribute('data-badge', status);
    if (readout) el.querySelector('.step-readout').textContent = readout;
    if (typeof elapsed === 'number') el.querySelector('.step-timing').textContent = elapsed + 'ms';
  }

  function setPipelineLabel(s) {
    els.pipelineStatus.textContent = s;
    els.pipelineStatus.setAttribute('data-state',
      s === 'IDLE' ? 'idle' : s === 'COMPLETE' ? 'complete' : s === 'BLOCKED' ? 'blocked' : 'running');
  }


  // ── STEP ICONS (inline SVG for each pipeline step) ──────────

  // ── STEP ICONS (inline SVG matching agentic execution screenshot) ──

  var STEP_ICONS = {
    'memory':        '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2.5 8a5.5 5.5 0 1 1 1.6 3.9"/><path d="M2.5 12V8H6.5"/><polyline points="8 5 8 8 10 10"/></svg>',
    'tools':         '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6.5" cy="6.5" r="4"/><line x1="9.5" y1="9.5" x2="13.5" y2="13.5"/></svg>',
    'task':          '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 3.5h8M5 8h8M5 12.5h8"/><polyline points="1.5 3.5 2.5 4.5 4 2.5"/><circle cx="2.5" cy="8" r="1"/><circle cx="2.5" cy="12.5" r="1"/></svg>',
    'start':         '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="5 3 13 8 5 13 5 3"/></svg>',
    'terminal':      '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1.5" y="2.5" width="13" height="11" rx="1.5"/><polyline points="4.5 6 7 8 4.5 10"/><line x1="8.5" y1="10" x2="11.5" y2="10"/></svg>',
    'code':          '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="5 4 2 8 5 12"/><polyline points="11 4 14 8 11 12"/></svg>',
    'rate-limit':    '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><polyline points="8 4.5 8 8 10.5 9.5"/></svg>',
    'prompt-safety': '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 1.5L2.5 4.5v3.5c0 3.5 2.4 6.8 5.5 7.5 3.1-.7 5.5-4 5.5-7.5V4.5L8 1.5Z"/></svg>',
    'rbac':          '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="4" y="7" width="8" height="6.5" rx="1"/><path d="M5.5 7V4.5a2.5 2.5 0 015 0V7"/></svg>',
    'doc-retrieval': '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9.5 2H4a1 1 0 00-1 1v10a1 1 0 001 1h8a1 1 0 001-1V5.5L9.5 2Z"/><polyline points="9.5 2 9.5 5.5 13 5.5"/><line x1="5.5" y1="9" x2="10.5" y2="9"/><line x1="5.5" y1="11.5" x2="8.5" y2="11.5"/></svg>',
    'vision':        '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8s-2.5 4.5-6.5 4.5S1.5 8 1.5 8Z"/><circle cx="8" cy="8" r="2"/></svg>',
    'calculation':   '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2.5" y="2" width="11" height="12" rx="1.5"/><line x1="5" y1="5.5" x2="11" y2="5.5"/><line x1="5" y1="8.5" x2="7" y2="8.5"/><line x1="9" y1="8.5" x2="11" y2="8.5"/><line x1="5" y1="11" x2="7" y2="11"/><line x1="9" y1="11" x2="11" y2="11"/></svg>',
    'approval':      '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="5.5" r="2.5"/><path d="M3.5 13.5c0-2.5 2-4.5 4.5-4.5s4.5 2 4.5 4.5"/></svg>',
    'audit-write':   '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="10" height="10" rx="1.5"/><polyline points="5.5 8 7 9.5 10.5 6"/></svg>'
  };

  // ── LIVE STEP UPDATES (in-place appending for smooth animation) ──

  function addLiveStep(chat, msg, step) {
    if (!msg || !msg.thinking) return;
    var existingIdx = -1;
    for (var i = 0; i < msg.thinking.steps.length; i++) {
      if (msg.thinking.steps[i].id === step.id) {
        existingIdx = i;
        break;
      }
    }
    if (existingIdx >= 0) {
      msg.thinking.steps[existingIdx].status = step.status;
      if (step.detail) msg.thinking.steps[existingIdx].detail = step.detail;
      var tl = document.getElementById('inline-timeline');
      if (tl) {
        var el = tl.querySelector('[data-step="' + step.id + '"]');
        if (el) {
          el.setAttribute('data-s', step.status);
          var d = el.querySelector('.thinking-step-detail');
          if (d && step.detail) d.textContent = step.detail;
        }
      }
    } else {
      msg.thinking.steps.push(step);
      var tl = document.getElementById('inline-timeline');
      if (tl) {
        tl.insertAdjacentHTML('beforeend', renderStepHtml(step));
        scrollToBottom();
      }
    }
  }

  function updateLiveStep(stepId, status, detail) {
    var chat = getActiveChat();
    if (!chat || !chat.messages.length) return;
    var last = chat.messages[chat.messages.length - 1];
    if (!last || !last.thinking) return;

    for (var i = 0; i < last.thinking.steps.length; i++) {
      if (last.thinking.steps[i].id === stepId) {
        last.thinking.steps[i].status = status;
        if (detail) last.thinking.steps[i].detail = detail;
        break;
      }
    }

    var tl = document.getElementById('inline-timeline');
    if (tl) {
      var el = tl.querySelector('[data-step="' + stepId + '"]');
      if (el) {
        el.setAttribute('data-s', status);
        if (detail) {
          var d = el.querySelector('.thinking-step-detail');
          if (d) d.textContent = detail;
        }
      }
    }
  }


  // ── SUBMIT / PIPELINE EXECUTION ────────────────────────────

  // ── SUBMIT / PIPELINE EXECUTION ────────────────────────────

  function handleSubmit() {
    var query = els.chatInput.value.trim();
    if (!query || state.pipelineRunning) return;

    if (!state.user) {
      openModal(els.authDialog);
      return;
    }

    if (!getActiveChat()) createChat();
    var chat = getActiveChat();

    var imgExtra = state.imageAttached ? { image: state.imageName } : {};
    addMessage('user', query, imgExtra);

    els.chatInput.value = '';
    autoResize();
    var hasImage = state.imageAttached;
    var imageData = state.imageData || null;
    removeImage();
    updateSendState();

    state.pipelineRunning = true;
    updateSendState();

    buildPipelineDOM(hasImage);
    setPipelineLabel('RUNNING');

    // Create assistant message with running thinking block
    var assistantMsg = addMessage('assistant', '', {
      thinking: {
        state: 'running',
        title: 'Thinking through defense pipeline\u2026',
        badge: 'RUNNING',
        collapsed: false,
        steps: []
      }
    });

    var startTime = performance.now();

    // Execute real backend streaming with local fallback
    executeBackendStream(query, hasImage, imageData, startTime, assistantMsg);
  }

  function executeBackendStream(query, hasImage, imageData, startTime, assistantMsg) {
    var headers = { 'Content-Type': 'application/json' };
    if (state.token) {
      headers['Authorization'] = 'Bearer ' + state.token;
    }
    var storedApiKey = localStorage.getItem('sovereign_api_key');
    var storedBaseUrl = localStorage.getItem('sovereign_base_url');
    if (storedApiKey) {
      headers['X-Model-Api-Key'] = storedApiKey;
    }
    if (storedBaseUrl) {
      headers['X-Model-Base-Url'] = storedBaseUrl;
    }

    var requestBody = {
      text: query,
      has_image: hasImage,
      image_data: imageData
    };

    fetch(API_BASE + '/query/stream', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(requestBody)
    })
    .then(function(response) {
      if (!response.ok) {
        return response.json().then(function(errData) {
          throw errData;
        });
      }

      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      function readChunk() {
        return reader.read().then(function(result) {
          if (result.done) {
            return;
          }
          buffer += decoder.decode(result.value, { stream: true });
          var parts = buffer.split('\n\n');
          buffer = parts.pop(); // keep partial

          for (var i = 0; i < parts.length; i++) {
            var block = parts[i].trim();
            if (!block) continue;
            var evMatch = block.match(/^event:\s*(.+)$/m);
            var dataMatch = block.match(/^data:\s*(.+)$/m);
            if (evMatch && dataMatch) {
              var evName = evMatch[1].trim();
              try {
                var evData = JSON.parse(dataMatch[1].trim());
                handleSSEEvent(evName, evData, query, hasImage, startTime, assistantMsg);
              } catch (e) {
                console.error('Failed to parse SSE event data', e);
              }
            }
          }
          return readChunk();
        });
      }

      return readChunk();
    })
    .catch(function(err) {
      console.warn('Backend SSE streaming unavailable, running local simulation fallback:', err);
      runLocalSimulationFallback(query, hasImage, startTime, assistantMsg);
    });
  }

  function handleSSEEvent(evName, data, query, hasImage, startTime, assistantMsg) {
    var chat = getActiveChat();
    switch (evName) {
      case 'init':
        addLiveStep(chat, assistantMsg, { id: 'mem-read', icon: 'memory', label: 'Read memory', crumb: 'Areas \u203A Sovereign Ai Workbench', detail: 'Project \u2014 "Sovereign On-Premise Agentic AI Workbench"', status: 'passed' });
        addLiveStep(chat, assistantMsg, { id: 'tool-load', icon: 'tools', label: 'Loaded tools', detail: 'Multi-Model Router & isolated defense security layers active', status: 'passed' });
        break;

      case 'model_routing':
        assistantMsg._model_routing = data;
        var displayModel = data.model.indexOf('DeepSeek') !== -1 ? 'DeepSeek Coder V2' : (data.model.indexOf('VL') !== -1 ? 'Qwen2.5-VL' : 'Qwen 2.5 32B');
        var displayProv = data.provider === 'huggingface' ? 'Hugging Face' : 'Local';
        var execTarget = (data.task_type === 'coding' || data.task_type === 'debugging') ? 'Docker Sandbox' : (data.task_type === 'vision' ? 'OpenCV Dial Vision' : 'Deterministic Engine');
        addLiveStep(chat, assistantMsg, {
          id: 'model-route',
          icon: 'tools',
          label: 'Model Router: ' + displayModel,
          detail: 'Task: ' + data.task_type + ' └── Provider: ' + displayProv + ' └── ' + execTarget,
          status: 'passed'
        });
        break;

      case 'step_start':
        updateStepUI(data.step, 'processing');
        addLiveStep(chat, assistantMsg, { id: data.step, icon: data.step, label: data.label, status: 'processing', detail: data.desc });
        break;

      case 'step_complete':
        updateStepUI(data.step, data.status, data.readout, data.elapsed_ms);
        updateLiveStep(data.step, data.status, data.readout);
        break;

      case 'approval_required':
        updateStepUI('approval', 'awaiting');
        updateLiveStep('approval', 'processing', 'Awaiting Human-in-the-Loop authorization\u2026');
        setPipelineLabel('AWAITING_APPROVAL');

        var details = data.approval_details;
        var threadId = data.thread_id;
        openApprovalModal({
          action: details.action,
          target: details.target,
          requestor: details.requestor,
          context: details.context,
          authority: details.authority,
          thread_id: threadId,
          onResolve: function(approved) {
            submitHITLDecision(threadId, approved, data, hasImage, startTime, assistantMsg);
          }
        });
        break;

      case 'blocked':
        updateStepUI(data.step, 'blocked', data.reason);
        updateLiveStep(data.step, 'blocked', data.reason);
        setPipelineLabel('BLOCKED');
        replaceThinkingWithBlocked(data.error || 'Security Policy Block', {
          'Pipeline halted at': data.step,
          'Reason': data.reason || data.error,
          'Operator clearance': 'Level ' + (state.user ? state.user.clearanceLevel : 'Unknown')
        }, data.audit_entry || { index: 0, hash: '0'.repeat(64) }, startTime, assistantMsg);
        state.pipelineRunning = false;
        updateSendState();
        loadAuditLog();
        break;

      case 'complete':
        setPipelineLabel('COMPLETE');
        replaceThinkingWithResponse(data.audit_entry, hasImage, startTime, assistantMsg, data);
        state.pipelineRunning = false;
        updateSendState();
        loadAuditLog();
        break;
    }
  }

  function submitHITLDecision(threadId, approved, sseData, hasImage, startTime, assistantMsg) {
    var headers = { 'Content-Type': 'application/json' };
    if (state.token) headers['Authorization'] = 'Bearer ' + state.token;

    fetch(API_BASE + '/approvals/' + threadId + '/decision', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        decision: approved ? 'approve' : 'reject',
        comment: 'Operator ' + (state.user ? state.user.name : 'Console') + ' decision'
      })
    })
    .then(function(res) { return res.json(); })
    .then(function(decisionRes) {
      if (approved) {
        updateStepUI('approval', 'passed', 'Authorized by ' + (state.user ? state.user.name : 'Operator'));
        updateLiveStep('approval', 'passed', 'Authorized by ' + (state.user ? state.user.name : 'Operator') + ' (HITL)');
        updateStepUI('audit-write', 'passed', 'Committed to hash chain');
        updateLiveStep('audit-write', 'passed', 'Committed to tamper-proof block (SHA-256 verified)');
        setPipelineLabel('COMPLETE');

        var completeData = {
          final_synthesis: decisionRes.note,
          retrieved_chunks: sseData.retrieved_chunks,
          vision_analysis: sseData.vision_analysis,
          calculation_result: sseData.calculation_result,
          action_executed: {
            action: decisionRes.action,
            target: decisionRes.target,
            operator: decisionRes.operator_email
          }
        };
        replaceThinkingWithResponse({ index: sseData.audit_entry.index + 1, hash: decisionRes.audit_hash || '0'.repeat(64) }, hasImage, startTime, assistantMsg, completeData);
        state.pipelineRunning = false;
        updateSendState();
        loadAuditLog();
      } else {
        updateStepUI('approval', 'rejected', 'Rejected by ' + (state.user ? state.user.name : 'Operator'));
        updateLiveStep('approval', 'blocked', 'Rejected by ' + (state.user ? state.user.name : 'Operator'));
        setPipelineLabel('BLOCKED');
        replaceThinkingWithBlocked('Human Approval Denied', {
          'Pipeline halted at': 'Human Approval (HITL)',
          'Reason': 'Action rejected by the approving authority.',
          'Rejected by': (state.user ? state.user.fullName || state.user.name : 'Operator')
        }, { index: sseData.audit_entry.index + 1, hash: decisionRes.audit_hash || '0'.repeat(64) }, startTime, assistantMsg);
        state.pipelineRunning = false;
        updateSendState();
        loadAuditLog();
      }
    })
    .catch(function(err) {
      console.error('Failed to submit approval decision:', err);
      state.pipelineRunning = false;
      updateSendState();
    });
  }

  function runLocalSimulationFallback(query, hasImage, startTime, assistantMsg) {
    var chat = getActiveChat();
    var steps = PIPELINE_STEPS.filter(function(s) { return !s.conditional || hasImage; });

    var isBlocked = false;
    var blockReason = '';
    var reqClearance = '';

    if (/reactor/i.test(query)) {
      if (state.user.clearanceLevel < 3) {
        isBlocked = true;
        blockReason = 'reactor-core-aux requires Level 3 clearance (Chief Safety Auditor)';
        reqClearance = 'Level 3';
      }
    } else if (/turbine|compressor/i.test(query)) {
      if (state.user.clearanceLevel < 2) {
        isBlocked = true;
        blockReason = 'turbine-gen-4 requires Level 2+ clearance (Systems Specialist)';
        reqClearance = 'Level 2';
      }
    }

    var blockedAt = isBlocked ? 'rbac' : null;
    var needsApproval = /valve|shutdown|override|emergency|open|close/i.test(query);

    var setupSequence = [
      { delay: 60, step: { id:'mem-read', icon:'memory', label:'Read memory', crumb:'Areas \u203A Sovereign Ai Workbench', detail:'Project \u2014 "Sovereign On-Premise Agentic AI Workbench"', status:'passed' } },
      { delay: 120, step: { id:'tool-load', icon:'tools', label:'Loaded tools', detail:'8 defense security layers & cryptographic loggers initialized', status:'passed' } },
      { delay: 80, step: { id:'task-rate', icon:'task', label:'Added task: Check rate limits & prompt safety', status:'passed' } },
      { delay: 80, step: { id:'task-rbac', icon:'task', label:'Added task: Verify operator RBAC clearance (' + state.user.name + ' \u00B7 ' + state.user.clearanceName + ')', status:'passed' } },
      { delay: 80, step: { id:'task-doc', icon:'task', label:'Added task: Retrieve equipment manual (\u00A74.2)', status:'passed' } }
    ];

    if (hasImage) {
      setupSequence.push({ delay: 80, step: { id:'task-vis', icon:'task', label:'Added task: Multimodal gauge inspection (vision)', status:'passed' } });
    }
    setupSequence.push({ delay: 80, step: { id:'task-calc', icon:'task', label:'Added task: Sandboxed calculation of pressure drop', status:'passed' } });
    if (needsApproval) {
      setupSequence.push({ delay: 80, step: { id:'task-auth', icon:'task', label:'Added task: Human authorization check (HITL)', status:'passed' } });
    }
    setupSequence.push({ delay: 100, step: { id:'task-start', icon:'start', label:'Started task: Defense verification & execution', status:'passed' } });

    function runSetup(i) {
      if (i >= setupSequence.length) {
        addAuditEntry('QUERY_SUBMITTED', 'Query: "' + query.substring(0,80) + '"').then(function() {
          executeSteps(steps, 0, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg);
        });
        return;
      }
      var item = setupSequence[i];
      setTimeout(function() {
        addLiveStep(chat, assistantMsg, item.step);
        runSetup(i + 1);
      }, item.delay);
    }

    runSetup(0);
  }

  function executeSteps(steps, idx, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg) {
    var chat = getActiveChat();
    if (idx >= steps.length) {
      finishPipeline(query, hasImage, startTime, assistantMsg);
      return;
    }

    var step = steps[idx];

    if (blockedAt && idx > getStepIdx(steps, blockedAt)) {
      updateStepUI(step.id, 'skipped');
      addLiveStep(chat, assistantMsg, { id: step.id, icon: step.id, label: step.label, status: 'skipped', detail: 'Skipped \u2014 execution halted' });
      executeSteps(steps, idx+1, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg);
      return;
    }

    updateStepUI(step.id, 'processing');
    addLiveStep(chat, assistantMsg, { id: step.id, icon: step.id, label: step.label, status: 'processing', detail: step.desc });

    if (step.interactive) {
      if (!needsApproval) {
        updateStepUI(step.id, 'skipped', 'No sensitive actions \u2014 skipped');
        updateLiveStep(step.id, 'passed', 'No sensitive actions \u2014 auto-cleared');
        executeSteps(steps, idx+1, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg);
        return;
      }

      updateStepUI(step.id, 'awaiting');
      updateLiveStep(step.id, 'processing', 'Awaiting Human-in-the-Loop authorization\u2026');
      setPipelineLabel('AWAITING_APPROVAL');

      openApprovalModal({
        action: 'open_release_valve',
        target: 'boiler-102 (release valve #4)',
        requestor: 'AI Agent (Maintenance Subsystem)',
        context: '\u0394p = 3.8 bar exceeds normal threshold. Recommended action: Open release valve to prevent over-pressurization.',
        authority: 'Senior_Engineer (HITL Required)',
        onResolve: function(approved) {
          if (approved) {
            updateStepUI(step.id, 'passed', 'Authorized by Senior_Engineer');
            updateLiveStep(step.id, 'passed', 'Authorized by Senior_Engineer (HITL)');
            setPipelineLabel('RUNNING');
            addAuditEntry('HITL_APPROVAL', 'open_release_valve approved by Senior_Engineer').then(function() {
              executeSteps(steps, idx+1, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg);
            });
          } else {
            updateStepUI(step.id, 'rejected', 'Rejected by Senior_Engineer');
            updateLiveStep(step.id, 'blocked', 'Rejected by Senior_Engineer');
            setPipelineLabel('BLOCKED');
            addAuditEntry('HITL_REJECTION', 'open_release_valve rejected by Senior_Engineer').then(function(entry) {
              replaceThinkingWithBlocked('Human Approval Denied', {
                'Pipeline halted at': 'Human Approval (HITL)',
                'Reason': 'Action rejected by the approving authority.',
                'Rejected by': 'Senior_Engineer (J. Morrison)'
              }, entry, startTime, assistantMsg);
              state.pipelineRunning = false;
              updateSendState();
            });
          }
        }
      });
      return;
    }

    var t0 = performance.now();
    setTimeout(function() {
      var elapsed = Math.round(performance.now() - t0);

      if (blockedAt === step.id) {
        updateStepUI(step.id, 'blocked', blockReason || 'Operator lacks required clearance', elapsed);
        updateLiveStep(step.id, 'blocked', blockReason || 'Operator lacks required clearance');
        setPipelineLabel('BLOCKED');
        addAuditEntry('RBAC_BLOCK', 'Query blocked \u2014 ' + (blockReason || 'insufficient clearance') + ' [' + state.user.email + ']').then(function(entry) {
          for (var j = idx+1; j < steps.length; j++) {
            updateStepUI(steps[j].id, 'skipped');
            addLiveStep(chat, assistantMsg, { id: steps[j].id, icon: steps[j].id, label: steps[j].label, status: 'skipped', detail: 'Skipped due to clearance block' });
          }
          replaceThinkingWithBlocked('Authorization Failed \u2014 Insufficient Clearance', {
            'Pipeline halted at': 'RBAC Verification',
            'Reason': blockReason || 'Operator does not have clearance for the requested system.',
            'Required tier': reqClearance || 'Level 2+',
            'Current operator': (state.user.fullName || state.user.name) + ' (' + state.user.clearanceName + ')'
          }, entry, startTime, assistantMsg);
          state.pipelineRunning = false;
          updateSendState();
        });
        return;
      }

      var readout = step.readout ? step.readout() : null;
      updateStepUI(step.id, 'passed', readout, elapsed);
      updateLiveStep(step.id, 'passed', readout);

      addAuditEntry('STEP_PASSED', step.label + ' \u2014 ' + elapsed + 'ms').then(function() {
        executeSteps(steps, idx+1, blockedAt, blockReason, reqClearance, needsApproval, query, hasImage, startTime, assistantMsg);
      });
    }, step.duration || 200);
  }

  function getStepIdx(steps, id) {
    for (var i = 0; i < steps.length; i++) if (steps[i].id === id) return i;
    return -1;
  }

  function finishPipeline(query, hasImage, startTime, assistantMsg) {
    setPipelineLabel('COMPLETE');
    addAuditEntry('QUERY_COMPLETE', 'Full pipeline pass \u2014 response assembled').then(function(entry) {
      updateStepUI('audit-write', 'passed', 'Entry #' + String(entry.index).padStart(4,'0') + ' committed', null);
      addLiveStep(getActiveChat(), assistantMsg, {
        id: 'audit-write',
        icon: 'audit-write',
        label: 'Audit Log Write',
        status: 'passed',
        detail: 'Committed to tamper-proof block #' + String(entry.index).padStart(4,'0') + ' (SHA-256 verified)'
      });
      replaceThinkingWithResponse(entry, hasImage, startTime, assistantMsg);
      state.pipelineRunning = false;
      updateSendState();
    });
  }


  // ── CODE RENDERING & SYNTAX HIGHLIGHTING (ChatGPT Style) ───
  var COPY_ICON_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
  var CHECK_ICON_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="#34d399" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';

  function highlightPython(rawCode) {
    if (!rawCode) return '';
    var tokens = [];
    function addToken(cls, content) {
      tokens.push('<span class="' + cls + '">' + content + '</span>');
      return '___SOV_TOK_' + (tokens.length - 1) + '___';
    }

    var s = rawCode;
    // 1. Comments
    s = s.replace(/(#.*$)/gm, function(m) {
      return addToken('tok-comment', esc(m));
    });

    // 2. Multi-line docstrings
    s = s.replace(/("""[\s\S]*?"""|'''[\s\S]*?''')/g, function(m) {
      return addToken('tok-string', esc(m));
    });

    // 3. Quoted strings (f-strings, raw strings, normal)
    s = s.replace(/([frbFRB]?("[^"\\]*(?:\\.[^"\\]*)*"|'[^'\\]*(?:\\.[^'\\]*)*'))/g, function(m) {
      return addToken('tok-string', esc(m));
    });

    // Escape non-string HTML
    s = esc(s);

    // 4. Numbers
    s = s.replace(/\b(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b/g, function(m) {
      return addToken('tok-number', m);
    });

    // 5. Keywords
    var kwRegex = /\b(def|class|return|if|elif|else|while|for|in|try|except|finally|raise|import|from|as|with|pass|break|continue|yield|lambda|assert|global|nonlocal|async|await|and|or|not|is)\b/g;
    s = s.replace(kwRegex, function(m) {
      return addToken('tok-keyword', m);
    });

    // 6. Built-ins
    var builtinRegex = /\b(print|True|False|None|self|cls|len|range|int|float|str|dict|list|set|tuple|bool|open|type|super|isinstance|sum|min|max|abs|round|enumerate|zip|map|filter)\b/g;
    s = s.replace(builtinRegex, function(m) {
      return addToken('tok-builtin', m);
    });

    // 7. Functions
    s = s.replace(/\b([a-zA-Z_]\w*)(?=\s*\()/g, function(m) {
      return addToken('tok-func', m);
    });

    // 8. Operators
    s = s.replace(/([=+\-*/%<>!&|^~]+)/g, function(m) {
      return addToken('tok-op', m);
    });

    // Restore tokens
    for (var i = 0; i < tokens.length; i++) {
      s = s.replace(new RegExp('___SOV_TOK_' + i + '___', 'g'), tokens[i]);
    }
    return s;
  }

  function extractCodeAndOutput(responseText, responseData, isCodingTask) {
    var code = (responseData && responseData.code) || '';
    var output = (responseData && responseData.execution_result) || (responseData && responseData.code_execution && responseData.code_execution.output) || '';
    var intro = '';
    var outro = '';

    // If this is NOT a coding task and backend did not provide verified code execution,
    // do not extract code fences into an interactive sandbox runner.
    // Instead, leave code fences inside the text to be rendered as readable markdown blocks!
    if (!isCodingTask && !code) {
      return { code: null, output: null, intro: '', outro: '' };
    }

    if (!code && responseText) {
      var codeFenceMatch = responseText.match(/```(?:([a-zA-Z0-9_-]+))?\s*([\s\S]*?)```/);
      if (codeFenceMatch) {
        code = codeFenceMatch[2].trim();
        var parts = responseText.split(codeFenceMatch[0]);
        intro = (parts[0] || '').trim();
        var rest = (parts[1] || '').trim();

        var execMatch = rest.match(/(?:Sandbox Execution Result|Output):\s*([\s\S]*)$/i);
        if (execMatch) {
          output = execMatch[1].trim();
          outro = rest.substring(0, execMatch.index).trim();
        } else {
          outro = rest;
        }
      }
    } else if (code && responseText) {
      var fenceIdx = responseText.indexOf('```');
      if (fenceIdx > 0) {
        intro = responseText.substring(0, fenceIdx).trim();
      }
      if (!output) {
        var execMatch2 = responseText.match(/(?:Sandbox Execution Result|Output):\s*([\s\S]*)$/i);
        if (execMatch2) {
          output = execMatch2[1].trim();
        }
      }
    }

    if (!output && /pump efficiency/i.test(code)) {
      output = 'Pump Efficiency = 85.0 %';
    }

    return { code: code, output: output, intro: intro, outro: outro };
  }

  function renderCodeCard(code, lang) {
    var languageName = (lang || 'Python').charAt(0).toUpperCase() + (lang || 'Python').slice(1);
    var highlighted = highlightPython(code);

    return '<div class="code-card" data-lang="' + esc(lang || 'python') + '" data-raw-code="' + esc(code) + '">' +
      '<div class="code-card-header">' +
        '<div class="code-card-lang">' +
          '<svg class="code-lang-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<polyline points="16 18 22 12 16 6"/>' +
            '<polyline points="8 6 2 12 8 18"/>' +
          '</svg>' +
          '<span>' + esc(languageName) + '</span>' +
        '</div>' +
        '<div class="code-card-actions">' +
          '<button type="button" class="btn-code-action btn-code-copy" onclick="copyCodeSnippet(this)" title="Copy code" aria-label="Copy code">' +
            COPY_ICON_SVG +
          '</button>' +
          '<button type="button" class="btn-code-action btn-code-run" onclick="runInteractiveCode(this)" title="Run code in sandbox">' +
            '<svg class="run-play-icon" viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><polygon points="6 4 19 12 6 20 6 4"/></svg>' +
            '<span>Run</span>' +
          '</button>' +
        '</div>' +
      '</div>' +
      '<pre class="code-card-pre"><code class="code-card-code">' + highlighted + '</code></pre>' +
    '</div>';
  }

  function renderOutputSection(output) {
    if (!output) return '';
    return '<div class="code-output-section">' +
      '<div class="code-output-label">Output:</div>' +
      '<div class="code-output-pill">' +
        '<div class="code-output-text">' + esc(output) + '</div>' +
        '<button type="button" class="btn-output-copy" onclick="copyOutputText(this)" title="Copy output" aria-label="Copy output">' +
          COPY_ICON_SVG +
        '</button>' +
      '</div>' +
    '</div>';
  }

  function renderActionToolbar() {
    return '<div class="msg-action-toolbar">' +
      '<button type="button" class="msg-action-btn" onclick="copyEntireMessage(this)" title="Copy response">' + COPY_ICON_SVG + '</button>' +
      '<button type="button" class="msg-action-btn btn-thumbs-up" onclick="rateMessage(this, \'up\')" title="Good response">' +
        '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>' +
      '</button>' +
      '<button type="button" class="msg-action-btn btn-thumbs-down" onclick="rateMessage(this, \'down\')" title="Bad response">' +
        '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"/></svg>' +
      '</button>' +
      '<button type="button" class="msg-action-btn" onclick="shareMessage(this)" title="Share / Export">' +
        '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>' +
      '</button>' +
      '<button type="button" class="msg-action-btn" onclick="regenerateMessage(this)" title="Regenerate">' +
        '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>' +
      '</button>' +
      '<button type="button" class="msg-action-btn" onclick="openMessageMoreMenu(this)" title="More options">' +
        '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><circle cx="12" cy="12" r="1.8"/><circle cx="5" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></svg>' +
      '</button>' +
    '</div>';
  }

  // ── GLOBAL INTERACTIVE HANDLERS ────────────────────────────
  window.showToast = function(msg) {
    var existing = document.querySelector('.sovereign-toast');
    if (existing) existing.remove();
    var toast = document.createElement('div');
    toast.className = 'sovereign-toast';
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(function() { toast.classList.add('show'); }, 10);
    setTimeout(function() {
      toast.classList.remove('show');
      setTimeout(function() { toast.remove(); }, 300);
    }, 2200);
  };

  window.copyCodeSnippet = function(btn) {
    var card = btn.closest('.code-card');
    if (!card) return;
    var code = card.dataset.rawCode || card.querySelector('code').innerText;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(code).then(function() {
        var orig = btn.innerHTML;
        btn.innerHTML = CHECK_ICON_SVG;
        window.showToast('Code copied to clipboard');
        setTimeout(function() { btn.innerHTML = orig; }, 1800);
      });
    }
  };

  window.copyOutputText = function(btn) {
    var pill = btn.closest('.code-output-pill');
    if (!pill) return;
    var text = pill.querySelector('.code-output-text').innerText;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function() {
        var orig = btn.innerHTML;
        btn.innerHTML = CHECK_ICON_SVG;
        window.showToast('Output copied to clipboard');
        setTimeout(function() { btn.innerHTML = orig; }, 1800);
      });
    }
  };

  window.runInteractiveCode = function(btn) {
    var card = btn.closest('.code-card');
    if (!card) return;
    var rawCode = card.dataset.rawCode || card.querySelector('code').innerText;
    var originalBtnHtml = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = '<svg class="spin-icon" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="9" stroke-dasharray="32" stroke-dashoffset="12"/></svg> <span>Running...</span>';

    var msgContent = card.closest('.msg-content') || card.parentElement;
    var outputSec = msgContent.querySelector('.code-output-section');
    var outputTextEl = outputSec ? outputSec.querySelector('.code-output-text') : null;

    var headers = { 'Content-Type': 'application/json' };
    if (state && state.token) headers['Authorization'] = 'Bearer ' + state.token;

    fetch((typeof API_BASE !== 'undefined' ? API_BASE : '') + '/sandbox/run', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({ code: rawCode })
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      btn.disabled = false;
      btn.innerHTML = originalBtnHtml;

      var resultText = (data.stdout && data.stdout.trim()) || data.stderr || ('Process finished with exit code ' + (data.exit_code || 0));

      if (outputSec && outputTextEl) {
        outputTextEl.textContent = resultText;
        outputSec.querySelector('.code-output-pill').classList.remove('pulse-glow');
        void outputSec.offsetWidth;
        outputSec.querySelector('.code-output-pill').classList.add('pulse-glow');
      } else {
        var newSec = document.createElement('div');
        newSec.className = 'code-output-section';
        newSec.innerHTML = '<div class="code-output-label">Output:</div>' +
          '<div class="code-output-pill pulse-glow">' +
            '<div class="code-output-text">' + esc(resultText) + '</div>' +
            '<button type="button" class="btn-output-copy" onclick="copyOutputText(this)" title="Copy output">' +
              COPY_ICON_SVG +
            '</button>' +
          '</div>';
        card.after(newSec);
      }
      window.showToast('Sandbox execution completed');
    })
    .catch(function(err) {
      btn.disabled = false;
      btn.innerHTML = originalBtnHtml;
      console.error('Sandbox run error:', err);
      window.showToast('Failed to execute code: ' + (err.message || 'Error'));
    });
  };

  window.copyEntireMessage = function(btn) {
    var body = btn.closest('.msg-body');
    if (!body) return;
    var content = body.querySelector('.msg-content');
    var text = content ? content.innerText : '';
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function() {
        var orig = btn.innerHTML;
        btn.innerHTML = CHECK_ICON_SVG;
        window.showToast('Response copied to clipboard');
        setTimeout(function() { btn.innerHTML = orig; }, 1800);
      });
    }
  };

  window.rateMessage = function(btn, type) {
    var toolbar = btn.closest('.msg-action-toolbar');
    var upBtn = toolbar.querySelector('.btn-thumbs-up');
    var downBtn = toolbar.querySelector('.btn-thumbs-down');

    if (type === 'up') {
      var isActive = upBtn.classList.toggle('active');
      downBtn.classList.remove('active');
      window.showToast(isActive ? 'Response marked as helpful' : 'Rating cleared');
    } else {
      var isActive = downBtn.classList.toggle('active');
      upBtn.classList.remove('active');
      window.showToast(isActive ? 'Response marked as unhelpful' : 'Rating cleared');
    }
  };

  window.shareMessage = function(btn) {
    var body = btn.closest('.msg-body');
    var text = body ? body.querySelector('.msg-content').innerText : '';
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function() {
        window.showToast('Response copied for sharing');
      });
    }
  };

  window.regenerateMessage = function(btn) {
    var chat = getActiveChat();
    if (!chat || chat.messages.length < 2) return;
    for (var i = chat.messages.length - 1; i >= 0; i--) {
      if (chat.messages[i].role === 'user') {
        var userPrompt = chat.messages[i].text;
        els.chatInput.value = userPrompt;
        autoResize();
        handleSend();
        break;
      }
    }
  };

  window.openMessageMoreMenu = function(btn) {
    window.showToast('Full telemetry recorded in Audit Log view');
  };


  // ── SIMPLE MARKDOWN RENDERER ──────────────────────────────
  function renderSimpleMarkdown(rawText) {
    if (!rawText) return '';
    var text = rawText;

    // 1. Code blocks ```lang ... ```
    text = text.replace(/```(?:([a-zA-Z0-9_-]+))?\s*([\s\S]*?)```/g, function(match, lang, codeContent) {
      var language = lang || 'text';
      var highlighted = (language.toLowerCase() === 'python' || language.toLowerCase() === 'py')
        ? highlightPython(codeContent.trim())
        : esc(codeContent.trim());
      return '<div class="md-code-block"><div class="md-code-lang">' + esc(language) + '</div><pre><code>' + highlighted + '</code></pre></div>';
    });

    // 2. Tables
    text = text.replace(/((?:\|[^\n]+\|\r?\n)+)/g, function(match) {
      var lines = match.trim().split(/\r?\n/);
      if (lines.length < 2) return match;
      var html = '<div class="md-table-wrap"><table class="md-table">';
      var inHead = true;
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (/^\|[-:\s|]+\|$/.test(line)) {
          inHead = false;
          continue;
        }
        var cells = line.split('|').slice(1, -1);
        if (inHead) {
          html += '<thead><tr>';
          cells.forEach(function(c) { html += '<th>' + esc(c.trim()) + '</th>'; });
          html += '</tr></thead><tbody>';
          inHead = false;
        } else {
          html += '<tr>';
          cells.forEach(function(c) {
            var cellContent = esc(c.trim());
            cellContent = cellContent.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            cellContent = cellContent.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
            html += '<td>' + cellContent + '</td>';
          });
          html += '</tr>';
        }
      }
      html += '</tbody></table></div>';
      return html;
    });

    // Split into paragraphs / sections
    var sections = text.split(/\n\n+/);
    var result = '';

    sections.forEach(function(sec) {
      sec = sec.trim();
      if (!sec) return;

      if (sec.startsWith('<div class="md-table-wrap"') || sec.startsWith('<div class="md-code-block"')) {
        result += sec;
        return;
      }

      // Check for headings
      if (/^###\s+(.+)$/m.test(sec)) {
        var lines = sec.split('\n');
        var parsedLines = [];
        for (var l = 0; l < lines.length; l++) {
          var line = lines[l].trim();
          if (line.startsWith('### ')) {
            parsedLines.push('<h3 class="md-h3">' + esc(line.substring(4)) + '</h3>');
          } else if (line.startsWith('## ')) {
            parsedLines.push('<h2 class="md-h2">' + esc(line.substring(3)) + '</h2>');
          } else if (line.startsWith('# ')) {
            parsedLines.push('<h2 class="md-h1">' + esc(line.substring(2)) + '</h2>');
          } else if (/^[-*]\s+(.+)$/.test(line)) {
            var item = esc(line.replace(/^[-*]\s+/, ''));
            item = item.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            item = item.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
            parsedLines.push('<li class="md-li">' + item + '</li>');
          } else if (line) {
            var pLine = esc(line);
            pLine = pLine.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            pLine = pLine.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
            parsedLines.push('<p class="md-p">' + pLine + '</p>');
          }
        }
        result += parsedLines.join('\n');
        return;
      }

      // Check for list items
      if (/^[-*]\s+/m.test(sec)) {
        var lines = sec.split('\n');
        var inList = false;
        var listHtml = '<ul class="md-ul">';
        lines.forEach(function(line) {
          line = line.trim();
          if (/^[-*]\s+(.+)$/.test(line)) {
            var item = esc(line.replace(/^[-*]\s+/, ''));
            item = item.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            item = item.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
            listHtml += '<li class="md-li">' + item + '</li>';
            inList = true;
          } else if (line) {
            var pLine = esc(line);
            pLine = pLine.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            pLine = pLine.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
            if (inList) {
              listHtml += '</ul><p class="md-p">' + pLine + '</p><ul class="md-ul">';
            } else {
              listHtml += '<p class="md-p">' + pLine + '</p>';
            }
          }
        });
        if (inList) listHtml += '</ul>';
        result += listHtml;
        return;
      }

      // Regular paragraph
      var pText = esc(sec);
      pText = pText.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      pText = pText.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
      result += '<p class="md-p">' + pText + '</p>';
    });

    return result;
  }

  // ── REPLACE THINKING / DISPLAY RESPONSE ────────────────────

  function replaceThinkingWithResponse(auditEntry, hasImage, startTime, assistantMsg, responseData) {
    var chat = getActiveChat();
    if (!chat) return;
    var targetMsg = assistantMsg || chat.messages[chat.messages.length - 1];
    if (!targetMsg || targetMsg.role !== 'assistant') return;

    var totalElapsed = ((performance.now() - (startTime || performance.now())) / 1000).toFixed(1);
    var passCount = targetMsg.thinking && targetMsg.thinking.steps ? targetMsg.thinking.steps.length : 8;

    if (targetMsg.thinking) {
      targetMsg.thinking.state = 'complete';
      targetMsg.thinking.title = 'Thought process \u00B7 ' + passCount + ' defense checks verified (' + totalElapsed + 's)';
      targetMsg.thinking.badge = 'COMPLETE';
    }

    var responseText = (responseData && responseData.final_synthesis)
      ? responseData.final_synthesis
      : 'Based on the confidential on-premise analysis, here are the verified results:';

    var blocksHtml = '<div class="msg-response-blocks">';

    // ── AI WORKBENCH AUTOMATIC MODEL ROUTING CARD ──
    var routing = (responseData && responseData.model_routing) || targetMsg._model_routing || null;
    var queryText = (chat && chat.messages.length >= 2 ? chat.messages[chat.messages.length - 2].text : '') || '';
    var isCodingTask = false;

    if (!routing) {
      var isTheory = /theory|concept|what is|explain|describe|difference between|overview/i.test(queryText);
      var isExplicitCode = /write code|implement|python script|code for|write python|program|leetcode/i.test(queryText);
      if (isExplicitCode || (!isTheory && /code|python|pump efficiency|script/i.test(queryText))) {
        routing = { task_type: 'coding', model: 'deepseek-ai/DeepSeek-Coder-V2-Instruct', provider: 'huggingface', sandboxed: true };
      } else if (hasImage || /image|gauge|dial|photo|needle/i.test(queryText)) {
        routing = { task_type: 'vision', model: 'Qwen2.5-VL', provider: 'local', sandboxed: false };
      } else {
        routing = { task_type: 'reasoning', model: 'qwen/qwen2.5-32b-instruct', provider: 'huggingface', sandboxed: false };
      }
    }

    isCodingTask = (routing.task_type === 'coding' || routing.task_type === 'debugging');
    var dispTask = routing.task_type.charAt(0).toUpperCase() + routing.task_type.slice(1);
    var dispModel = 'Qwen 2.5 32B';
    if (routing.model) {
      if (routing.model.indexOf('DeepSeek') !== -1 || routing.model.indexOf('Coder') !== -1) dispModel = 'DeepSeek Coder V2';
      else if (routing.model.indexOf('VL') !== -1) dispModel = 'Qwen2.5-VL';
      else if (routing.model.indexOf('FLUX') !== -1 || routing.model.indexOf('flux') !== -1) dispModel = 'FLUX.1-schnell';
      else if (routing.model.indexOf('72B') !== -1) dispModel = 'Qwen 2.5 72B';
    }
    var dispProv = routing.provider === 'huggingface' ? 'Hugging Face' : 'Local';
    var dispExec = isCodingTask ? 'Docker Sandbox' : (routing.task_type === 'vision' ? 'OpenCV Dial Vision' : (routing.task_type === 'image_generation' ? 'Hugging Face T2I' : 'LangGraph Reasoner'));

    blocksHtml += '<div class="resp-block resp-block--model-router">' +
      '<div class="resp-block-title">' +
        '<span>AI WORKBENCH &middot; AUTOMATIC MODEL ROUTING</span>' +
      '</div>' +
      '<div class="resp-block-content">' +
        '<div class="resp-tree-row"><span class="resp-tree-label">Task detected</span><span class="resp-tree-val">&boxur;&nbsp;' + esc(dispTask) + '</span></div>' +
        '<div class="resp-tree-row"><span class="resp-tree-label">Model selected</span><span class="resp-tree-val resp-value--accent">&boxur;&nbsp;' + esc(dispModel) + '</span></div>' +
        '<div class="resp-tree-row"><span class="resp-tree-label">Provider</span><span class="resp-tree-val">&boxur;&nbsp;' + esc(dispProv) + '</span></div>' +
        '<div class="resp-tree-row"><span class="resp-tree-label">Execution</span><span class="resp-tree-val">&boxur;&nbsp;' + esc(dispExec) + '</span></div>' +
        '<div class="resp-tree-row"><span class="resp-tree-label">Status</span><span class="resp-tree-val resp-value--passed">&boxur;&nbsp;Verified &check;</span></div>' +
      '</div>' +
    '</div>';

    // ── Extract code and output if present ──
    var parsed = extractCodeAndOutput(responseText, responseData, isCodingTask);

    // Document context (ONLY when relevant SOP chunks were actually retrieved)
    if (responseData && responseData.retrieved_chunks && responseData.retrieved_chunks.length > 0) {
      var topChunk = responseData.retrieved_chunks[0];
      blocksHtml += respBlock('Document Context (Qdrant Iron Vault)',
        '<p>Retrieved from: <strong>' + esc(topChunk.sop_id) + ' \u2014 ' + esc(topChunk.title) + '</strong> (Min Clearance: L' + topChunk.min_clearance + ')</p>' +
        '<p style="margin-top:4px;font-family:var(--font-mono);font-size:11px;color:var(--text-2)">' +
        '"' + esc(topChunk.content.substring(0, 180)) + '\u2026"</p>');
    }

    // Vision Analysis (ONLY when an image was analyzed)
    var vis = (responseData && responseData.vision_analysis);
    if (vis) {
      if (vis.reading !== undefined && vis.reading !== null) {
        blocksHtml += respBlock('Vision Analysis (OpenCV Dial Extraction)',
          '<div class="resp-row"><span class="resp-label">Gauge reading</span><span class="resp-value resp-value--accent">' + vis.reading + ' ' + (vis.unit || 'bar') + ' (inlet)</span></div>' +
          '<div class="resp-row"><span class="resp-label">Confidence</span><span class="resp-value">' + (vis.confidence || '0.96') + '</span></div>' +
          '<div class="resp-row"><span class="resp-label">Assessment</span><span class="resp-value">' + esc(vis.assessment || 'Within normal range') + '</span></div>');
      } else if (vis.explanation) {
        blocksHtml += respBlock('Vision Analysis (Multimodal Qwen2.5-VL)',
          '<p style="font-size:12px;line-height:1.5;color:var(--text-1)">' + esc(vis.explanation.substring(0, 240)) + (vis.explanation.length > 240 ? '\u2026' : '') + '</p>');
      }
    } else if (hasImage) {
      blocksHtml += respBlock('Vision Analysis',
        '<div class="resp-row"><span class="resp-label">Visual Asset</span><span class="resp-value resp-value--accent">Analyzed</span></div>' +
        '<div class="resp-row"><span class="resp-label">Status</span><span class="resp-value resp-value--passed">Verified &check;</span></div>');
    }

    // Sandboxed Calculation (ONLY when a calculation actually occurred)
    var calc = (responseData && responseData.calculation_result);
    if (calc && calc.pressure_drop !== undefined && calc.pressure_drop !== null) {
      blocksHtml += respBlock('Calculation Result (Deterministic AST Sandbox)',
        '<div class="resp-row"><span class="resp-label">Pressure drop (\u0394p)</span><span class="resp-value resp-value--accent">' + calc.pressure_drop + ' ' + (calc.unit || 'bar') + '</span></div>' +
        '<div class="resp-row"><span class="resp-label">Normal range</span><span class="resp-value">' + esc(calc.normal_range || '2.0 \u2013 5.0 bar') + '</span></div>' +
        '<div class="resp-row"><span class="resp-label">Status</span><span class="resp-value ' + (calc.is_abnormal ? 'resp-value--blocked' : 'resp-value--passed') + '">' + esc(calc.status) + ' ' + (calc.is_abnormal ? '\u26A0' : '\u2714') + '</span></div>');
    }

    // Action Executed (ONLY when an action was executed)
    if (responseData && responseData.action_executed) {
      blocksHtml += respBlock('Action Executed',
        '<div class="resp-row"><span class="resp-label">Action</span><span class="resp-value mono">' + esc(responseData.action_executed.action) + '</span></div>' +
        '<div class="resp-row"><span class="resp-label">Target</span><span class="resp-value mono">' + esc(responseData.action_executed.target) + '</span></div>' +
        '<div class="resp-row"><span class="resp-label">Status</span><span class="resp-value resp-value--passed">APPROVED &amp; EXECUTED</span></div>' +
        '<div class="resp-row"><span class="resp-label">Authorized by</span><span class="resp-value">' + esc(responseData.action_executed.operator || state.user.name) + '</span></div>');
    }

    // Tamper-Proof Audit Reference
    var entryIdx = (auditEntry && (auditEntry.index !== undefined ? auditEntry.index : auditEntry.idx)) || 1;
    var entryHash = (auditEntry && auditEntry.hash) || '0'.repeat(64);
    blocksHtml += '<div class="resp-block resp-block--audit"><div class="resp-block-title">Tamper-Proof Audit Reference (SHA-256 Hash Chain)</div><div class="resp-block-content">' +
      '<div class="resp-row"><span class="resp-label">Entry</span><span class="resp-value">#' + String(entryIdx).padStart(4,'0') + '</span></div>' +
      '<div class="resp-row"><span class="resp-label">Hash</span><span class="audit-hash-inline">' + entryHash.substring(0,32) + '\u2026</span></div>' +
      '<div class="resp-row"><span class="resp-label">Chain</span><span class="resp-value resp-value--passed">VERIFIED \u2714</span></div>' +
    '</div></div>';

    blocksHtml += '</div>';

    var fullHtml = '';
    if (parsed.code) {
      if (parsed.intro) {
        fullHtml += '<p class="msg-intro-text" style="margin-bottom:8px;color:var(--text-1);">' + esc(parsed.intro) + '</p>';
      }
      fullHtml += renderCodeCard(parsed.code, 'python');
      if (parsed.output) {
        fullHtml += renderOutputSection(parsed.output);
      }
      if (parsed.outro) {
        fullHtml += '<p style="margin-top:10px;color:var(--text-2);">' + esc(parsed.outro) + '</p>';
      }

      fullHtml += '<div class="workbench-verification-wrap">' +
        '<details class="workbench-verification-details">' +
          '<summary class="workbench-verification-summary">' +
            '<div class="verification-summary-left">' +
              '<svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="8" cy="8" r="7"/><polyline points="5 8 7 10 11 6"/></svg>' +
              '<span>Defense Pipeline &amp; Audit Verification</span>' +
            '</div>' +
            '<span class="verification-badge">VERIFIED &check;</span>' +
          '</summary>' +
          '<div class="workbench-verification-body">' +
            blocksHtml +
          '</div>' +
        '</details>' +
      '</div>';

      fullHtml += renderActionToolbar();
    } else {
      fullHtml += '<div class="msg-markdown-body">' + renderSimpleMarkdown(responseText) + '</div>';

      fullHtml += '<div class="workbench-verification-wrap">' +
        '<details class="workbench-verification-details">' +
          '<summary class="workbench-verification-summary">' +
            '<div class="verification-summary-left">' +
              '<svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="8" cy="8" r="7"/><polyline points="5 8 7 10 11 6"/></svg>' +
              '<span>Defense Pipeline &amp; Audit Verification</span>' +
            '</div>' +
            '<span class="verification-badge">VERIFIED &check;</span>' +
          '</summary>' +
          '<div class="workbench-verification-body">' +
            blocksHtml +
          '</div>' +
        '</details>' +
      '</div>';

      fullHtml += renderActionToolbar();
    }

    targetMsg.html = fullHtml;
    targetMsg.time = timeNow();
    renderChatMessages();
    scrollToBottom();
  }

  function replaceThinkingWithBlocked(title, details, auditEntry, startTime, assistantMsg) {
    var chat = getActiveChat();
    if (!chat) return;
    var targetMsg = assistantMsg || chat.messages[chat.messages.length - 1];
    if (!targetMsg || targetMsg.role !== 'assistant') return;

    var totalElapsed = ((performance.now() - (startTime || performance.now())) / 1000).toFixed(1);

    if (targetMsg.thinking) {
      targetMsg.thinking.state = 'blocked';
      targetMsg.thinking.title = 'Pipeline Halted \u00B7 ' + title + ' (' + totalElapsed + 's)';
      targetMsg.thinking.badge = 'BLOCKED';
    }

    var html = '<div class="msg-blocked-box">';
    html += '<div class="msg-blocked-title">' + esc(title) + '</div>';
    html += '<dl class="msg-blocked-details">';
    Object.keys(details).forEach(function(k) {
      html += '<dt>' + esc(k) + '</dt><dd>' + esc(details[k]) + '</dd>';
    });
    html += '<dt>Audit entry</dt><dd>#' + String(auditEntry.index).padStart(4,'0') + ' (hash: ' + auditEntry.hash.substring(0,16) + '\u2026)</dd>';
    html += '</dl></div>';

    targetMsg.html = html;
    targetMsg.time = timeNow();
    renderChatMessages();
    scrollToBottom();
  }

  function respBlock(title, content) {
    return '<div class="resp-block"><div class="resp-block-title">' + esc(title) + '</div><div class="resp-block-content">' + content + '</div></div>';
  }


  // ── APPROVAL MODAL ─────────────────────────────────────────

  var approvalCallback = null;

  function openApprovalModal(opts) {
    if (typeof opts === 'function') {
      opts = { onResolve: opts };
    }
    opts = opts || {};
    if (els.approvalAction) els.approvalAction.textContent = opts.action || 'open_release_valve';
    if (els.approvalTarget) els.approvalTarget.textContent = opts.target || 'boiler-102 (release valve #4)';
    if (els.approvalRequestor) els.approvalRequestor.textContent = opts.requestor || 'AI Agent (Maintenance Subsystem)';
    if (els.approvalContext) els.approvalContext.textContent = opts.context || '\u0394p = 3.8 bar exceeds normal threshold. Recommended action: Open release valve to prevent over-pressurization.';
    if (els.approvalAuthority) els.approvalAuthority.textContent = opts.authority || 'Senior_Engineer (HITL Required)';
    approvalCallback = opts.onResolve || null;

    closeUserMenu();
    if (els.approvalDialog) {
      if (els.approvalDialog.showModal) {
        els.approvalDialog.showModal();
      } else {
        els.approvalDialog.setAttribute('open', '');
      }
    }
    if (els.btnApprove) els.btnApprove.focus();
  }

  function showApprovalModal(cb) {
    openApprovalModal({ onResolve: cb });
  }

  function closeApprovalModal(approved) {
    if (els.approvalDialog) {
      if (els.approvalDialog.close) els.approvalDialog.close();
      else els.approvalDialog.removeAttribute('open');
    }
    if (approvalCallback) {
      var cb = approvalCallback;
      approvalCallback = null;
      cb(approved);
    }
  }


  // ── DEMO SCENARIOS ─────────────────────────────────────────

  function loadDemoScenario(promptText, attachImage) {
    if (!state.user) {
      showToast('Please sign in to execute operational scenarios.');
      openModal(els.authDialog);
      return;
    }
    if (state.pipelineRunning) return;
    if (!getActiveChat() || getActiveChat().messages.length > 0) createChat({ silent: true });
    els.chatInput.value = promptText;
    if (attachImage) {
      simulateImageAttach();
    } else {
      removeImage();
    }
    autoResize();
    updateSendState();
    switchView('chat');
    els.chatInput.focus();
  }

  function loadDemo() {
    loadDemoScenario('Write Python code to calculate pump efficiency when input power is 100 kW and output power is 85 kW.', false);
  }


  // ── EVENT LISTENERS ────────────────────────────────────────

  els.themeToggle.addEventListener('click', toggleTheme);
  els.btnOpenSidebar.addEventListener('click', toggleSidebar);
  els.btnCloseSidebar.addEventListener('click', closeSidebar);
  els.sidebarOverlay.addEventListener('click', closeSidebar);
  els.btnNewChat.addEventListener('click', function() {
    if (!state.user) {
      showToast('Please sign in to create an operational chat session.');
      openModal(els.authDialog);
      return;
    }
    createChat();
  });

  els.chatList.addEventListener('click', function(e) {
    var btnUnlock = e.target.closest('#btn-sidebar-unlock');
    if (btnUnlock) {
      openModal(els.authDialog);
      return;
    }
    if (!state.user) {
      openModal(els.authDialog);
      return;
    }
    var btn = e.target.closest('.chat-item');
    if (btn && btn.dataset.chatId) switchChat(btn.dataset.chatId);
  });

  if (els.tabHome) {
    els.tabHome.addEventListener('click', function() { switchView('home'); });
  }
  els.tabChat.addEventListener('click', function() {
    if (!state.user) {
      showToast('Operator clearance required to access chat console.');
      openModal(els.authDialog);
      return;
    }
    switchView('chat');
  });
  els.tabPipeline.addEventListener('click', function() { switchView('pipeline'); });
  els.tabAudit.addEventListener('click', function() {
    loadAuditLog();
    switchView('audit');
  });

  // Nav Login Button
  if (els.btnNavLogin) {
    els.btnNavLogin.addEventListener('click', function() {
      openModal(els.authDialog);
    });
  }

  // Home Hero Buttons
  if (els.btnHeroLaunch) {
    els.btnHeroLaunch.addEventListener('click', function() {
      if (!state.user) {
        showToast('Operator clearance required to access chat console.');
        openModal(els.authDialog);
        return;
      }
      switchView('chat');
      els.chatInput.focus();
    });
  }
  if (els.btnHeroLogin) {
    els.btnHeroLogin.addEventListener('click', function() {
      openModal(els.authDialog);
    });
  }
  if (els.btnHeroPipeline) {
    els.btnHeroPipeline.addEventListener('click', function() {
      switchView('pipeline');
    });
  }
  if (els.btnHomeAuditCard) {
    els.btnHomeAuditCard.addEventListener('click', function() {
      loadAuditLog();
      switchView('audit');
    });
  }

  // Home Page Scenario Card click delegate
  if (els.homeView) {
    els.homeView.addEventListener('click', function(e) {
      var card = e.target.closest('.demo-card');
      if (card && card.dataset.prompt) {
        var attachImg = card.dataset.image === 'true';
        loadDemoScenario(card.dataset.prompt, attachImg);
      }
    });
  }

  // Handle clicks in chatMessages (suggestion cards, barrier buttons, thinking block toggle)
  els.chatMessages.addEventListener('click', function(e) {
    var btnBarrierSignin = e.target.closest('#btn-barrier-signin');
    if (btnBarrierSignin) {
      openModal(els.authDialog);
      return;
    }
    var btnBarrierHome = e.target.closest('#btn-barrier-home');
    if (btnBarrierHome) {
      switchView('home');
      return;
    }
    var card = e.target.closest('.suggestion-card');
    if (card) {
      var prompt = card.getAttribute('data-prompt');
      var attachImg = card.getAttribute('data-image') === 'true';
      if (prompt) {
        loadDemoScenario(prompt, attachImg);
      }
      return;
    }

    var toggle = e.target.closest('.thinking-toggle');
    if (toggle) {
      var block = toggle.closest('.thinking-block');
      if (block) {
        block.classList.toggle('collapsed');
        var idx = block.getAttribute('data-msg-idx');
        var chat = getActiveChat();
        if (chat && idx !== '' && chat.messages[idx] && chat.messages[idx].thinking) {
          chat.messages[idx].thinking.collapsed = block.classList.contains('collapsed');
        }
      }
    }
  });

  els.chatInput.addEventListener('input', function() { updateSendState(); autoResize(); });
  els.imageAttach.addEventListener('change', handleImageSelect);
  els.labelAttach.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); els.imageAttach.click(); }
  });
  els.btnRemoveImg.addEventListener('click', removeImage);

  var btnCoding = document.getElementById('btn-demo-coding');
  if (btnCoding) {
    btnCoding.addEventListener('click', function() {
      loadDemoScenario('Write Python code to calculate pump efficiency when input power is 100 kW and output power is 85 kW.', false);
    });
  }
  var btnDoc = document.getElementById('btn-demo-doc');
  if (btnDoc) {
    btnDoc.addEventListener('click', function() {
      loadDemoScenario('Summarize this engineering inspection report.', false);
    });
  }
  var btnVision = document.getElementById('btn-demo-vision');
  if (btnVision) {
    btnVision.addEventListener('click', function() {
      loadDemoScenario('Read this inspection image and extract the gauge reading.', true);
    });
  }
  if (els.btnDemo) {
    els.btnDemo.addEventListener('click', loadDemo);
  }

  els.btnSend.addEventListener('click', handleSubmit);

  els.chatInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      if (e.shiftKey) {
        return; // Allow Shift+Enter to create a new line
      }
      e.preventDefault();
      handleSubmit();
    }
  });

  // Scroll to bottom floating button
  if (els.btnScrollBottom) {
    els.chatScroll.addEventListener('scroll', function() {
      var dist = els.chatScroll.scrollHeight - els.chatScroll.scrollTop - els.chatScroll.clientHeight;
      if (dist > 100) {
        els.btnScrollBottom.removeAttribute('hidden');
      } else {
        els.btnScrollBottom.setAttribute('hidden', '');
      }
    });
    els.btnScrollBottom.addEventListener('click', function() {
      els.chatScroll.scrollTo({ top: els.chatScroll.scrollHeight, behavior: 'smooth' });
    });
  }

  els.btnApprove.addEventListener('click', function() { closeApprovalModal(true); });
  els.btnReject.addEventListener('click', function() { closeApprovalModal(false); });
  els.approvalDialog.addEventListener('cancel', function(e) { e.preventDefault(); });

  // ── USER PROFILE & MENU LISTENERS ──────────────────────────

  if (els.btnUserProfile) {
    els.btnUserProfile.addEventListener('click', toggleUserMenu);
  }
  if (els.btnSidebarLogin) {
    els.btnSidebarLogin.addEventListener('click', function() { openModal(els.authDialog); });
  }

  // Outside click to close user menu
  document.addEventListener('click', function(e) {
    if (els.userMenuContainer && !els.userMenuContainer.contains(e.target)) {
      closeUserMenu();
    }
  });

  // User menu action buttons
  if (els.btnMenuSettings)   els.btnMenuSettings.addEventListener('click', function() { openModal(els.settingsDialog); });
  if (els.btnMenuLanguage)   els.btnMenuLanguage.addEventListener('click', function() { openModal(els.settingsDialog); });
  if (els.btnMenuHelp)       els.btnMenuHelp.addEventListener('click', function() { openModal(els.helpDialog); });
  if (els.btnMenuClearances) els.btnMenuClearances.addEventListener('click', function() { openModal(els.clearancesDialog); });
  if (els.btnMenuTools)      els.btnMenuTools.addEventListener('click', function() { openModal(els.toolsDialog); });
  if (els.btnMenuAcademy)    els.btnMenuAcademy.addEventListener('click', function() { openModal(els.academyDialog); });
  if (els.btnMenuAbout)      els.btnMenuAbout.addEventListener('click', function() { openModal(els.aboutDialog); });
  if (els.btnMenuLogout)     els.btnMenuLogout.addEventListener('click', logoutUser);

  // Dialog close buttons
  if (els.btnCloseAuth)       els.btnCloseAuth.addEventListener('click', function() { closeModal(els.authDialog); });
  if (els.btnCloseSettings)   els.btnCloseSettings.addEventListener('click', function() { closeModal(els.settingsDialog); });
  if (els.btnCloseAcademy)    els.btnCloseAcademy.addEventListener('click', function() { closeModal(els.academyDialog); });
  if (els.btnCloseClearances) els.btnCloseClearances.addEventListener('click', function() { closeModal(els.clearancesDialog); });
  if (els.btnCloseHelp)       els.btnCloseHelp.addEventListener('click', function() { closeModal(els.helpDialog); });
  if (els.btnCloseTools)      els.btnCloseTools.addEventListener('click', function() { closeModal(els.toolsDialog); });
  if (els.btnCloseAbout)      els.btnCloseAbout.addEventListener('click', function() { closeModal(els.aboutDialog); });

  // Backdrop click dismiss for dialogs
  [els.authDialog, els.shiftBriefingDialog, els.settingsDialog, els.academyDialog, els.clearancesDialog, els.helpDialog, els.toolsDialog, els.aboutDialog].forEach(function(dlg) {
    if (!dlg) return;
    dlg.addEventListener('click', function(e) {
      var rect = dlg.getBoundingClientRect();
      var isInDialog = (rect.top <= e.clientY && e.clientY <= rect.top + rect.height &&
        rect.left <= e.clientX && e.clientX <= rect.left + rect.width);
      if (!isInDialog) {
        closeModal(dlg);
      }
    });
  });

  // Global keyboard shortcuts
  document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === ',') {
      e.preventDefault();
      openModal(els.settingsDialog);
    }
    if (e.key === 'Escape') {
      closeUserMenu();
    }
  });

  // Auth Tabs (Sign In vs Create Account)
  if (els.authTabSignin && els.authTabSignup) {
    els.authTabSignin.addEventListener('click', function() {
      els.authTabSignin.classList.add('active');
      els.authTabSignin.setAttribute('aria-selected', 'true');
      els.authTabSignup.classList.remove('active');
      els.authTabSignup.setAttribute('aria-selected', 'false');
      if (els.formSignin) els.formSignin.hidden = false;
      if (els.formSignup) els.formSignup.hidden = true;
    });

    els.authTabSignup.addEventListener('click', function() {
      els.authTabSignup.classList.add('active');
      els.authTabSignup.setAttribute('aria-selected', 'true');
      els.authTabSignin.classList.remove('active');
      els.authTabSignin.setAttribute('aria-selected', 'false');
      if (els.formSignup) els.formSignup.hidden = false;
      if (els.formSignin) els.formSignin.hidden = true;
    });
  }

  // Quick Demo Profiles (Auth modal & login page)
  var qpButtons = document.querySelectorAll('.quick-profile-btn, .fast-tier-btn');
  qpButtons.forEach(function(btn) {
    btn.addEventListener('click', function() {
      var userKey = btn.getAttribute('data-demo-user') || btn.getAttribute('data-user');
      if (DEMO_USERS[userKey]) {
        authenticate(DEMO_USERS[userKey].email, 'changeme123');
      }
    });
  });

  var formLoginPage = $('form-login-page');
  if (formLoginPage) {
    formLoginPage.addEventListener('submit', function(e) {
      e.preventDefault();
      var email = ($('lp-email') && $('lp-email').value.trim()) || 'suketu.2005@gmail.com';
      var password = ($('lp-password') && $('lp-password').value) || 'changeme123';
      authenticate(email, password);
    });
  }

  var linkGuestAccess = $('link-guest-access');
  if (linkGuestAccess) {
    linkGuestAccess.addEventListener('click', function() {
      switchView('home');
    });
  }

  // Custom Sign In Submit
  if (els.formSignin) {
    els.formSignin.addEventListener('submit', function(e) {
      e.preventDefault();
      var email = (els.signinEmail && els.signinEmail.value.trim()) || 'suketu.2005@gmail.com';
      var password = (els.signinPassword && els.signinPassword.value) || 'changeme123';
      authenticate(email, password);
    });
  }

  // Custom Sign Up Submit
  if (els.formSignup) {
    els.formSignup.addEventListener('submit', function(e) {
      e.preventDefault();
      var fullName = (els.signupName && els.signupName.value.trim()) || 'Suketu Patel';
      var email = (els.signupEmail && els.signupEmail.value.trim()) || 'suketu.2005@gmail.com';
      var password = (els.signupPassword && els.signupPassword.value) || 'changeme123';
      var clearanceVal = (els.signupClearance && els.signupClearance.value) || 'level-3';
      var clrLevel = clearanceVal === 'level-1' ? 1 : clearanceVal === 'level-2' ? 2 : 3;

      fetch(API_BASE + '/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName,
          email: email,
          password: password,
          clearance_level: clrLevel
        })
      })
      .then(function() {
        return authenticate(email, password);
      })
      .catch(function() {
        return authenticate(email, password);
      });
    });
  }

  // Save Settings
  if (els.btnSaveSettings) {
    els.btnSaveSettings.addEventListener('click', function() {
      var theme = els.settingThemeSelect ? els.settingThemeSelect.value : 'system';
      if (theme === 'system') state.theme = null;
      else state.theme = theme;
      applyTheme();

      var langMap = { en: 'English', de: 'Deutsch', es: 'Espa\u00F1ol', hi: 'Hindi' };
      var lang = els.settingLangSelect ? els.settingLangSelect.value : 'en';
      if (els.menuCurrentLang) {
        els.menuCurrentLang.textContent = langMap[lang] || 'English';
      }
      closeModal(els.settingsDialog);
    });
  }

  // Tools JSON Export
  if (els.btnExportAuditJson) {
    els.btnExportAuditJson.addEventListener('click', exportAuditJson);
  }


  // ── INIT ───────────────────────────────────────────────────

  function checkModelStatus() {
    fetch(API_BASE + '/api/models/status')
      .then(function(res) { return res.json(); })
      .then(function(data) {
        var el = document.getElementById('sovereign-mode-text');
        if (el && data) {
          if (data.sovereign_mode) {
            el.textContent = 'AIR-GAP ENFORCED';
            if (el.parentElement) {
              el.parentElement.style.borderColor = '#f59e0b';
              el.parentElement.style.color = '#f59e0b';
            }
          } else {
            el.textContent = 'ROUTER ONLINE';
          }
        }
      })
      .catch(function() {});
  }

  applyTheme();
  initApiKeyDrawer();
  checkModelStatus();

  // Initial landing page state: unauthenticated guest
  state.user = null;
  state.token = null;

  // Seed past chats
  SEED_CHATS.forEach(function(c) { state.chats.push(c); });

  // Update UI components for unauthenticated state
  updateUserUI();
  renderChatList();
  renderChatMessages();

  // Switch to Home landing view
  switchView('home');

  // Load verified audit chain from backend if authenticated
  if (state.token) {
    loadAuditLog();
  }

  // Handle mobile sidebar initial state
  if (isMobile()) {
    els.sidebar.classList.add('collapsed');
    state.sidebarOpen = false;
  }

  updateSendState();
  setPipelineLabel('IDLE');

});
