const socket = io();

    function formatChallengeLabel(iqValue) {
      if (iqValue === undefined || iqValue === null) return null;
      const iq = Number(iqValue);
      if (!Number.isFinite(iq)) return null;
      if (iq >= 150) return "Expert";
      if (iq >= 130) return "Tough";
      return null;
    }
    
    // Confetti
    function fireConfetti() {
      var count = 200;
      var defaults = {
        origin: { y: 0.7 }
      };

      function fire(particleRatio, opts) {
        confetti(Object.assign({}, defaults, opts, {
          particleCount: Math.floor(count * particleRatio)
        }));
      }

      fire(0.25, {
        spread: 26,
        startVelocity: 55,
      });
      fire(0.2, {
        spread: 60,
      });
      fire(0.35, {
        spread: 100,
        decay: 0.91,
        scalar: 0.8
      });
      fire(0.1, {
        spread: 120,
        startVelocity: 25,
        decay: 0.92,
        scalar: 1.2
      });
      fire(0.1, {
        spread: 120,
        startVelocity: 45,
      });
    }

    // State
    let myUsername = localStorage.getItem('triviaUsername') || '';
    let isPlayer = false;
    let intermissionInterval;
    let timerInterval;
    let current_question_index = -1;
    let myScoreDisplayed = 0;
    let lastRoundByPlayer = {};
    let playerAnswered = false;
    let hostToken = null;
    let lastHostPingAt = 0;
    let serverTimeOffsetMs = 0;
    let hasTimeSync = false;
    let lastTimeSyncAt = 0;
    let timerTotalSeconds = 30;
    let specRingLength = 0;
    let playerRingLength = 0;
    let timerEndServerSeconds = null;
    let timerStartLocalMs = 0;
    let lastTimerEventAt = 0;
    let timerMode = 'question';

    // Elements
    const views = {
      spectator: document.getElementById('spectator-view'),
      player: document.getElementById('player-view')
    };
    
    const fabJoin = document.getElementById('fab-join');
    const inputUsername = document.getElementById('username-input');
    const joinStatus = document.getElementById('join-status');
    const gameOverOverlay = document.getElementById('game-over-overlay');
    const finalLeaderboard = document.getElementById('final-leaderboard');
    const btnNewGame = document.getElementById('btn-new-game');

    // --- NAVIGATION LOGIC ---
    function showView(viewName) {
      Object.values(views).forEach(el => el.classList.add('hidden'));
      views[viewName].classList.remove('hidden');
    }

    // Initial Load
    showView('spectator');
    if (myUsername) inputUsername.value = myUsername;

    const nowWithOffsetMs = () => Date.now() + serverTimeOffsetMs;
    const nowWithOffsetSeconds = () => nowWithOffsetMs() / 1000;

    const requestTimeSync = () => {
      socket.emit('time_ping', { client_ts: Date.now() });
    };

    // Join Flow
    // Removed separate join view logic

    const setJoinStatus = (message, isError = false) => {
      if (!joinStatus) return;
      if (!message) {
        joinStatus.classList.add('hidden');
        joinStatus.textContent = '';
        return;
      }
      joinStatus.textContent = message;
      joinStatus.classList.toggle('join-status-error', isError);
      joinStatus.classList.remove('hidden');
    };

    let pendingJoinName = null;

    // Add test confetti button logic if it exists (we will add it to DOM in a moment if not present, but for now let's just expose function)

    document.getElementById('btn-confirm-join').onclick = () => {
      const name = inputUsername.value.trim();
      if (!name) return setJoinStatus('Please enter a name.', true);
      if (!hostToken) {
        pendingJoinName = name;
        return setJoinStatus('Waiting for host session...', false);
      }
      
      myUsername = name;
      localStorage.setItem('triviaUsername', name);
      socket.emit('join', { username: name, host_token: hostToken });
    };
    
    socket.on('joined', (data) => {
      if (data.username === myUsername) {
        // Update UI
        isPlayer = true;
        document.getElementById('my-player-name').textContent = myUsername;
        showView('player');
      }
    });

    socket.on('player_joined', (data) => {
      fireConfetti();
    });

    if (joinStatus) {
      setJoinStatus('Waiting for host session...', false);
    }

    const tryPendingJoin = () => {
      if (pendingJoinName && hostToken) {
        const name = pendingJoinName;
        pendingJoinName = null;
        myUsername = name;
        localStorage.setItem('triviaUsername', name);
        socket.emit('join', { username: name, host_token: hostToken });
        setJoinStatus('', false);
      }
    };

    socket.on('host_session', (data) => {
      hostToken = data.token || null;
      lastHostPingAt = Date.now();
      if (hostToken) setJoinStatus('', false);
      tryPendingJoin();
      requestTimeSync();
    });

    socket.on('host_ping', (data) => {
      if (!hostToken || data.token === hostToken) {
        hostToken = data.token || hostToken;
        lastHostPingAt = Date.now();
        if (hostToken) setJoinStatus('', false);
        tryPendingJoin();
        requestTimeSync();
      }
    });

    setInterval(() => {
      if (!hostToken) return;
      if (Date.now() - lastHostPingAt > 180000) {
        hostToken = null;
        setJoinStatus('Waiting for host session...', false);
      }
    }, 3000);

    // --- REAL-TIME TYPING ---
    inputUsername.oninput = (e) => {
      socket.emit('typing_username', { username: e.target.value });
    };


    // --- SOCKET HANDLERS ---

    // 1. Player List & Leaderboard
    socket.on('player_list', (data) => {
      const list = document.getElementById('player-list');
      list.innerHTML = '';

      const entries = Object.entries(data.players);
      const rankMap = {};
      let lastScore = null;
      let lastRank = 0;
      entries.forEach(([name, stats], index) => {
        if (lastScore === stats.score) {
          rankMap[name] = lastRank;
        } else {
          lastRank = index + 1;
          rankMap[name] = lastRank;
          lastScore = stats.score;
        }
      });
      
      // Update Spectator Board
      for (const [name, stats] of entries) {
        const li = document.createElement('li');
        let nameHtml = `<span class="player-name">${name}</span>`;
        if (data.winning_players && data.winning_players.includes(name) && stats.score > 0) nameHtml += ' 👑';
        if (lastRoundByPlayer[name] === true) nameHtml += ' ✅';
        if (lastRoundByPlayer[name] === false) nameHtml += ' ❌';
        
        li.innerHTML = `${nameHtml} <span class="player-score">${stats.score}</span>`;
        list.appendChild(li);
      }

      // Update Player Status (if playing)
      if (isPlayer) {
        const myStats = data.players[myUsername];
        const myScore = myStats ? myStats.score : 0;
        const myRank = rankMap[myUsername];
        const rankLabel = Number.isFinite(myRank) ? `#${myRank}` : '';
        const hasScore = myScore > 0;
        const isWinning = hasScore && data.winning_players && data.winning_players.includes(myUsername);

            const scoreEl = document.getElementById('my-player-score');
        const startScore = myScoreDisplayed;
        const endScore = myScore;

        const animateScore = (from, to, durationMs) => {
          const start = performance.now();
          const step = (now) => {
            const progress = Math.min(1, (now - start) / durationMs);
            const value = Math.round(from + (to - from) * progress);
            const rankHtml = rankLabel ? `${rankLabel}${isWinning ? ' 👑' : ''}` : '';
            scoreEl.innerHTML = `${value}`;
            const nameEl = document.getElementById('my-player-name');
            if (nameEl) {
              nameEl.innerHTML = rankLabel ? `${rankHtml}<br>${myUsername}` : myUsername;
            }
            if (progress < 1) requestAnimationFrame(step);
          };
          requestAnimationFrame(step);
        };

        if (endScore !== startScore) {
          const delta = Math.abs(endScore - startScore);
          const duration = Math.min(1200, Math.max(300, delta * 30));
          animateScore(startScore, endScore, duration);
          myScoreDisplayed = endScore;
        } else {
          const rankHtml = rankLabel ? `${rankLabel}${isWinning ? ' 👑' : ''}` : '';
          scoreEl.innerHTML = `${endScore}`;
          const nameEl = document.getElementById('my-player-name');
          if (nameEl) {
            nameEl.innerHTML = rankLabel ? `${rankHtml}<br>${myUsername}` : myUsername;
          }
        }

        if (!rankLabel) {
          const nameEl = document.getElementById('my-player-name');
          if (nameEl) {
            nameEl.textContent = myUsername;
          }
        }
      }
    });

    socket.on('update_joining_players', (names) => {
        const container = document.getElementById('joining-players-container');
        // Filter out self
        const others = names.filter(n => n !== inputUsername.value);
        if (others.length > 0) {
            container.textContent = `Joining: ${others.join(', ')}...`;
        } else {
            container.textContent = '';
        }
    });


    const startCountdown = (endTimeSeconds, durationSeconds) => {
      if (timerInterval) clearInterval(timerInterval);
      timerEndServerSeconds = endTimeSeconds;
      timerStartLocalMs = Date.now();
      if (!hasTimeSync) {
        requestTimeSync();
      }
      if (Number.isFinite(durationSeconds)) {
        timerTotalSeconds = Math.round(durationSeconds);
      } else if (Number.isFinite(endTimeSeconds)) {
        timerTotalSeconds = Math.round(endTimeSeconds - nowWithOffsetSeconds());
      } else {
        timerTotalSeconds = 30;
      }
      if (!Number.isFinite(timerTotalSeconds) || timerTotalSeconds <= 1 || timerTotalSeconds > 120) {
        timerTotalSeconds = 30;
      }
      setTimerMode("question");
      document.getElementById('spectator-timer').classList.remove('hidden');
      document.getElementById('player-timer').classList.remove('hidden');
      const nextTimer = document.getElementById('next-question-timer');
      if (nextTimer) nextTimer.classList.add('hidden');

      const updateTimer = () => {
        const now = nowWithOffsetSeconds();
        const elapsedLocalSeconds = (Date.now() - timerStartLocalMs) / 1000;
        const remainingLocalRaw = timerTotalSeconds - elapsedLocalSeconds;
        const remainingServerRaw = Number.isFinite(timerEndServerSeconds)
          ? (timerEndServerSeconds - now)
          : NaN;
        const remainingLocal = Math.max(0, remainingLocalRaw);
        const remainingServer = Math.max(0, remainingServerRaw);
        const useServer = hasTimeSync && Number.isFinite(remainingServer) && remainingServer <= 120;
        const remaining = useServer ? remainingServer : remainingLocal;
        
        if (remaining <= 0) {
          clearInterval(timerInterval);
          if (isPlayer) {
            document.querySelectorAll('.answer-btn').forEach(b => b.disabled = true);
          }
          document.getElementById('spectator-timer').classList.add('hidden');
          document.getElementById('player-timer').classList.add('hidden');
          return;
        }

        const ratio = Math.max(0, Math.min(1, remaining / timerTotalSeconds));
        setRingProgress('spectator-ring', specRingLength, ratio);
        setRingProgress('player-ring', playerRingLength, ratio);
        const urgent = timerMode === 'question' && remaining > 0 && remaining <= 5;
        document.getElementById('spectator-timer').classList.toggle('urgent', urgent);
        document.getElementById('player-timer').classList.toggle('urgent', urgent);

        const decimalRemaining = Math.max(0, remaining);
        setTimerDisplay(decimalRemaining);
      };

      updateTimer();
      timerInterval = setInterval(updateTimer, 100);
    };

    // 2. Game Flow: Timer
    socket.on('timer', (payload) => {
      lastTimerEventAt = Date.now();
      const endTime = payload.end_time;
      const durationSeconds = payload.duration;
      if (!Number.isFinite(endTime) || !Number.isFinite(durationSeconds)) {
        return;
      }
      startCountdown(endTime, durationSeconds);
    });


    // 3. Game Flow: Question
    socket.on('question', (data) => {
      if (intermissionInterval) clearInterval(intermissionInterval);
      playerAnswered = false;
      current_question_index = data.index;
      document.getElementById('scoreboard').classList.add('hidden');
      document.getElementById('btn-start').classList.add('hidden');
      document.getElementById('btn-next').classList.add('hidden');

      const questionReceivedAt = Date.now();
      setTimeout(() => {
        if (!lastTimerEventAt || lastTimerEventAt < questionReceivedAt) {
          startCountdown(null, 30);
          setTimerMode("question");
        }
      }, 200);
      
      // Spectator View
      document.getElementById('spectator-question').innerHTML = data.question;
      const spectatorIq = document.getElementById('spectator-iq');
      if (spectatorIq) {
        const label = formatChallengeLabel(data.iq);
        spectatorIq.textContent = label || "";
        spectatorIq.classList.toggle('hidden', !label);
        spectatorIq.classList.remove('iq-pop');
        void spectatorIq.offsetWidth;
        spectatorIq.classList.add('iq-pop');
      }
      const specList = document.getElementById('spectator-answers');
      specList.innerHTML = '';
      data.answers.forEach((ans, idx) => {
        const li = document.createElement('li');
        const div = document.createElement('button');
        div.type = 'button';
        div.className = 'answer-btn non-interactive';
        const letter = String.fromCharCode(65 + idx);
        const span = document.createElement('span');
        span.innerHTML = `${letter}:&nbsp;&nbsp;${ans}`;
        div.appendChild(span);
        li.appendChild(div);
        specList.appendChild(li);
      });
      
      // Update Button Text
//      document.getElementById('btn-next').textContent = "Stop Timer";

      // Player View
      if (isPlayer) {
        document.getElementById('player-question-text').innerHTML = data.question;
        const playerIq = document.getElementById('player-iq');
        if (playerIq) {
          const label = formatChallengeLabel(data.iq);
          playerIq.textContent = label || "";
          playerIq.classList.toggle('hidden', !label);
          playerIq.classList.remove('iq-pop');
          void playerIq.offsetWidth;
          playerIq.classList.add('iq-pop');
        }
        const btnContainer = document.getElementById('player-buttons');
        btnContainer.innerHTML = '';
        
        data.answers.forEach((ans, idx) => {
          const btn = document.createElement('button');
          btn.className = 'answer-btn';
          const letter = String.fromCharCode(65 + idx);
          const span = document.createElement('span');
          span.innerHTML = `${letter}:&nbsp;&nbsp;${ans}`;
          btn.appendChild(span);
          btn.onclick = () => {
            if (playerAnswered) return;
            socket.emit('answer', { username: myUsername, answer_index: idx });
            document.querySelectorAll('.answer-btn').forEach(b => {
              b.disabled = true;
              b.classList.add('dimmed');
            });
            btn.classList.add('selected');
            btn.classList.remove('dimmed');
            playerAnswered = true;
          };
          btnContainer.appendChild(btn);
        });
      }
    });


    // 4. Game Flow: Results
    socket.on('round_results', (data) => {
      document.getElementById('scoreboard').classList.remove('hidden');
      if (timerInterval) clearInterval(timerInterval);
      if (intermissionInterval) clearInterval(intermissionInterval);
      setRingProgress('spectator-ring', specRingLength, 0);
      setRingProgress('player-ring', playerRingLength, 0);
      document.getElementById('spectator-timer').classList.add('hidden');
      document.getElementById('player-timer').classList.add('hidden');
      setTimerDisplay(0);
      setTimerMode("question");

      const correctText = data.answers[data.correct_index];
      const correctLetter = String.fromCharCode(65 + data.correct_index);
      const fullCorrectText = `${correctLetter}: ${correctText}`;
      
      // Show next button when results are displayed
      const btnNext = document.getElementById('btn-next');
      btnNext.classList.remove('hidden');
      btnNext.onclick = () => socket.emit('next_question', current_question_index + 1);
      const playerCountdown = document.getElementById('player-next-countdown');
      if (playerCountdown) playerCountdown.classList.remove('hidden');
      
      if (data.next_question_time) {
          const updateCountdown = () => {
              const secondsLeft = Math.ceil(data.next_question_time - nowWithOffsetSeconds());
              if (secondsLeft > 0) {
                  btnNext.textContent = `Next question in ${secondsLeft} seconds`;
                  if (playerCountdown) {
                    playerCountdown.textContent = `Next question in ${secondsLeft} seconds`;
                  }
              } else {
                  btnNext.textContent = "Loading Next Question...";
                  if (playerCountdown) {
                    playerCountdown.textContent = "Loading Next Question...";
                  }
                  if (intermissionInterval) clearInterval(intermissionInterval);
              }
          };
          updateCountdown();
          intermissionInterval = setInterval(updateCountdown, 1000);
      } else {
          btnNext.textContent = "Next question";
          if (playerCountdown) {
            playerCountdown.textContent = "Next question";
          }
          setTimerDisplay(0);
          setRingProgress('spectator-ring', specRingLength, 0);
          setRingProgress('player-ring', playerRingLength, 0);
          setTimerMode("question");
      }
      
      // Spectator: Show detailed results
      const specList = document.getElementById('spectator-answers');
      const specButtons = specList.querySelectorAll('.answer-btn');
      if (specButtons.length === data.answers.length) {
        specButtons.forEach((btn, idx) => {
          btn.classList.toggle('correct', idx === data.correct_index);
          btn.classList.toggle('incorrect', idx !== data.correct_index);
        });
      }
      
      // Player: Show personal result
      if (isPlayer && data.player_answers[myUsername]) {
         const myResult = data.player_answers[myUsername];
         if (myResult.is_correct) {
            fireConfetti();
         } else {
            const area = document.getElementById('player-question-area');
            if (area) {
              area.classList.add('sad');
              setTimeout(() => area.classList.remove('sad'), 1600);
            }
            const buttons = document.querySelectorAll('#player-buttons .answer-btn');
            const correctBtn = buttons[data.correct_index];
            if (correctBtn) {
              correctBtn.classList.add('flash-correct');
              setTimeout(() => correctBtn.classList.remove('flash-correct'), 1800);
            }
         }
         const playerButtons = document.querySelectorAll('#player-buttons .answer-btn');
         if (playerButtons.length === data.answers.length) {
           playerButtons.forEach((btn, idx) => {
             btn.classList.toggle('correct', idx === data.correct_index);
             btn.classList.toggle('incorrect', idx !== data.correct_index);
           });
         }
      }

      lastRoundByPlayer = {};
      for (const [name, result] of Object.entries(data.player_answers || {})) {
        lastRoundByPlayer[name] = !!result.is_correct;
      }
    });

    socket.on('game_started', () => {
      document.getElementById('btn-start').classList.add('hidden');
      document.getElementById('btn-next').classList.add('hidden');
      lastRoundByPlayer = {};
      document.getElementById('scoreboard').classList.add('hidden');
      if (gameOverOverlay) gameOverOverlay.classList.add('hidden');
    });

    socket.on('game_reset', () => {
      window.location.reload();
    });

    socket.on('game_over', (finalScores) => {
       if (timerInterval) clearInterval(timerInterval);
       document.getElementById('btn-next').classList.add('hidden');
       document.getElementById('btn-start').classList.remove('hidden');
       setTimerDisplay(0);
       setRingProgress('spectator-ring', specRingLength, 0);
       setRingProgress('player-ring', playerRingLength, 0);
       document.getElementById('spectator-timer').classList.remove('hidden');
       document.getElementById('player-timer').classList.remove('hidden');
       setTimerMode("question");
       document.getElementById('scoreboard').classList.remove('hidden');

       if (gameOverOverlay && finalLeaderboard) {
         finalLeaderboard.innerHTML = '';
         const entries = Object.entries(finalScores || {}).sort((a, b) => b[1].score - a[1].score);
         entries.forEach(([name, stats], idx) => {
           const li = document.createElement('li');
           const rank = idx + 1;
           li.innerHTML = `<span class="final-rank">#${rank}</span><span class="final-name">${name}</span><span class="final-score">${stats.score}</span>`;
           finalLeaderboard.appendChild(li);
         });
         gameOverOverlay.classList.remove('hidden');
       }

       if (btnNewGame) {
         btnNewGame.classList.toggle('hidden', isPlayer);
       }
    });

    socket.on('clear_question', () => {
      if (timerInterval) clearInterval(timerInterval);
      document.getElementById('spectator-question').textContent = "Waiting for game to start...";
      const spectatorIq = document.getElementById('spectator-iq');
      if (spectatorIq) spectatorIq.classList.add('hidden');
      document.getElementById('spectator-answers').innerHTML = "";
      setTimerDisplay(0);
      document.getElementById('player-question-text').textContent = "Waiting for game to start...";
      const playerIq = document.getElementById('player-iq');
      if (playerIq) playerIq.classList.add('hidden');
      document.getElementById('player-buttons').innerHTML = "";
      setTimerDisplay(0);
      setRingProgress('spectator-ring', specRingLength, 0);
      setRingProgress('player-ring', playerRingLength, 0);
      document.getElementById('spectator-timer').classList.remove('hidden');
      document.getElementById('player-timer').classList.remove('hidden');
      setTimerMode("question");
      lastRoundByPlayer = {};
      document.getElementById('scoreboard').classList.remove('hidden');
      if (gameOverOverlay) gameOverOverlay.classList.add('hidden');
    });

    socket.on('connect', () => {
      requestTimeSync();
    });

    socket.on('gamestate', (data) => {
      const state = data && data.state;
      if (!state) return;
      document.body.dataset.gamestate = state;
      const radios = document.querySelectorAll('input[name="gamestate"]');
      radios.forEach((radio) => {
        radio.checked = radio.value === state;
      });
    });

    socket.on('time_pong', (data) => {
      const clientSent = data.client_ts;
      const serverTs = data.server_ts;
      if (typeof clientSent !== 'number' || typeof serverTs !== 'number') return;
      const now = Date.now();
      const rtt = now - clientSent;
      const estimatedServerAtReceive = serverTs * 1000 + (rtt / 2);
      serverTimeOffsetMs = estimatedServerAtReceive - now;
      hasTimeSync = true;
      lastTimeSyncAt = now;
      if (!Number.isFinite(timerTotalSeconds) || timerTotalSeconds <= 1 || timerTotalSeconds > 120) {
        if (Number.isFinite(timerEndServerSeconds)) {
          timerTotalSeconds = Math.max(1, Math.round(timerEndServerSeconds - nowWithOffsetSeconds()));
        }
      }
    });

    socket.on('error', (err) => setJoinStatus(err.message || 'Connection error', true));

    // --- QR Toggle ---
    const qrContainer = document.getElementById('qr-container');
    const qrCode = document.getElementById('qr-code');
    const qrToggle = document.getElementById('qr-toggle');
    if (qrCode && qrContainer) {
      qrCode.addEventListener('click', () => {
        qrContainer.classList.toggle('qr-large');
      });
    }
    if (qrToggle && qrContainer) {
      qrToggle.addEventListener('click', () => {
        const isShown = qrContainer.classList.toggle('show-on-small');
        qrToggle.textContent = isShown ? 'Hide QR' : 'Show QR';
      });
    }


    // --- Spectator BUTTONS ---
    document.getElementById('btn-start').onclick = () => socket.emit('start_game');
    document.getElementById('btn-next').onclick = () => socket.emit('next_question', current_question_index + 1);
    document.getElementById('btn-restart').onclick = () => {
      socket.emit('reset_all');
    };
    const btnConfetti = document.getElementById('btn-confetti');
    if (btnConfetti) {
      btnConfetti.onclick = () => fireConfetti();
    }
    const gamestateRadios = document.querySelectorAll('input[name="gamestate"]');
    gamestateRadios.forEach((radio) => {
      radio.addEventListener('change', () => {
        if (!radio.checked) return;
        if (!hostToken) return;
        socket.emit('set_gamestate', { state: radio.value, host_token: hostToken });
      });
    });
    if (btnNewGame) {
      btnNewGame.onclick = () => socket.emit('reset_all');
    }

    const setRingProgress = (ringId, length, ratio) => {
      const ring = document.getElementById(ringId);
      if (!ring || length === 0) return;
      const clamped = Math.max(0, Math.min(1, ratio));
      ring.style.strokeDashoffset = `${length * (1 - clamped)}`;
    };

    const setTimerDisplay = (seconds) => {
      const safeSeconds = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
      const intPart = Math.floor(safeSeconds);
      const decPart = Math.floor((safeSeconds - intPart) * 10);
      const intText = String(intPart);
      const markup = `<span class="timer-int">${intText}</span><span class="timer-dec">.${decPart}</span>`;
      const spec = document.getElementById('spectator-time');
      const player = document.getElementById('player-time');
      if (spec) spec.innerHTML = markup;
      if (player) player.innerHTML = markup;
    };

    const setTimerMode = (mode) => {
      timerMode = mode;
      const specTimer = document.getElementById('spectator-timer');
      const playerTimer = document.getElementById('player-timer');
      [specTimer, playerTimer].forEach((el) => {
        if (!el) return;
        el.classList.toggle('intermission', mode === 'intermission');
      });
    };

    const initRings = () => {
      const specRing = document.getElementById('spectator-ring');
      const playerRing = document.getElementById('player-ring');
      if (specRing) {
        specRingLength = 2 * Math.PI * specRing.r.baseVal.value;
        specRing.style.strokeDasharray = `${specRingLength}`;
        specRing.style.strokeDashoffset = `${specRingLength}`;
      }
      if (playerRing) {
        playerRingLength = 2 * Math.PI * playerRing.r.baseVal.value;
        playerRing.style.strokeDasharray = `${playerRingLength}`;
        playerRing.style.strokeDashoffset = `${playerRingLength}`;
      }
    };

    initRings();
    setTimerDisplay(0);
