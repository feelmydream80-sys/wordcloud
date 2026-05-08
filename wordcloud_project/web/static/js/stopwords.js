document.addEventListener('DOMContentLoaded', function() {
    // Toast notification
    const toastEl = document.getElementById('toast-notification');
    const toast = new bootstrap.Toast(toastEl);

    // Loading indicator
    const loadingIndicator = document.getElementById('loading-indicator');
    const stopwordsTableContainer = document.getElementById('stopwords-table-container');
    const noResults = document.getElementById('no-results');

    // DOM elements
    const categoryList = document.getElementById('category-list');
    const statistics = document.getElementById('statistics');
    const stopwordsTableBody = document.getElementById('stopwords-table-body');
    const categorySelect = document.getElementById('new-category-select');
    const autoClassifyBtn = document.getElementById('auto-classify-btn');
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const newWordInput = document.getElementById('new-word-input');
    const addBtn = document.getElementById('add-btn');
    const demoTextInput = document.getElementById('demo-text-input');
    const demoFilterBtn = document.getElementById('demo-filter-btn');
    const demoResults = document.getElementById('demo-results');
    const demoOriginal = document.getElementById('demo-original');
    const demoFiltered = document.getElementById('demo-filtered');
    const demoStats = document.getElementById('demo-stats');

    // State
    let allStopwords = [];
    let allCategories = []; // 전체 카테고리 목록
    let totalStopwords = 0; // 전체 불용어 수
    let currentCategory = null;
    let searchTerm = '';
    let currentPage = 1;
    let pageSize = 10;
    let totalPages = 1;

    // Initialize
    initialize();

    async function initialize() {
        try {
            await Promise.all([
                loadStopwords(),
                loadCategories()
            ]);
            updateUI();
            updateStatistics();
            updatePagination();
        } catch (error) {
            showToast('error', '초기화 실패', error.message);
        }
    }

    async function loadStopwords() {  // 페이징 매개변수 제거
        try {
            console.log('=== loadStopwords() called ===');
            const url = `/api/stopwords`;
            console.log('Fetching from URL:', url);
            
            const response = await fetch(url);
            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);
            
            // Read response as text first to check encoding
            const text = await response.text();
            console.log('Response text:', text);
            
            const data = JSON.parse(text);
            console.log('Parsed data:', data);
            
            if (data.success) {
                allStopwords = data.stopwords;
                totalStopwords = data.total; // 전체 불용어 수
                allCategories = data.categories; // 전체 카테고리 목록
                
                console.log('All stopwords loaded:', allStopwords);
                console.log('Total stopwords:', totalStopwords);
                console.log('All categories:', allCategories);
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            console.error('Error loading stopwords:', error);
            allStopwords = [];
            throw error;
        }
    }

    function getWordCategory(word) {
        // Find the category for a word from the loaded data
        const stopwordItem = allStopwords.find(item => item.word === word);
        return stopwordItem ? stopwordItem.category : '기타';
    }

    async function loadCategories() {
        try {
            const response = await fetch('/api/stopwords/categories');
            const data = await response.json();
            if (data.success) {
                allCategories = data.categories; // 전체 카테고리 목록 저장
                updateCategoryList(data.categories);
                updateCategorySelect(data.categories);
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            console.error('Error loading categories:', error);
            throw error;
        }
    }

    function updateCategoryList(categories) {
        categoryList.innerHTML = '';
        
        // 전체 카테고리 항목
        const allItem = document.createElement('div');
        allItem.className = 'category-item' + (currentCategory === null ? ' active' : '');
        allItem.textContent = '전체';
        allItem.addEventListener('click', () => {
            currentCategory = null;
            updateCategoryList(categories);
            updateUI();
            updateStatistics();
        });
        categoryList.appendChild(allItem);

        // 개별 카테고리 항목
        categories.forEach(category => {
            const item = document.createElement('div');
            item.className = 'category-item' + (currentCategory === category ? ' active' : '');
            item.textContent = category;
            item.addEventListener('click', () => {
                currentCategory = category;
                updateCategoryList(categories);
                updateUI();
                updateStatistics();
            });
            categoryList.appendChild(item);
        });
        
        console.log('Category list updated with currentCategory:', currentCategory);
    }

    function updateCategorySelect(categories) {
        categorySelect.innerHTML = '';
        
        categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            categorySelect.appendChild(option);
        });
    }

    function updateUI() {
        // Filter stopwords
        let filteredStopwords = [...allStopwords];
        
        if (currentCategory) {
            filteredStopwords = filteredStopwords.filter(item => item.category === currentCategory);
        }

        if (searchTerm) {
            filteredStopwords = filteredStopwords.filter(item => 
                item.word.toLowerCase().includes(searchTerm.toLowerCase())
            );
        }

        // Apply pagination
        const startIndex = (currentPage - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        const paginatedStopwords = filteredStopwords.slice(startIndex, endIndex);

        // Update table
        if (filteredStopwords.length > 0) {
            showTable(paginatedStopwords);
            updatePagination(filteredStopwords.length);
        } else {
            showNoResults();
        }
    }

    function showTable(stopwords) {
        stopwordsTableBody.innerHTML = '';
        
        stopwords.forEach(item => {
            const row = document.createElement('tr');
            row.className = 'fade-in';
            
            const wordCell = document.createElement('td');
            wordCell.textContent = item.word;
            
            const categoryCell = document.createElement('td');
            categoryCell.textContent = item.category;
            
            const actionCell = document.createElement('td');
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn btn-outline-danger action-btn delete-btn';
            deleteBtn.innerHTML = '<i class="fas fa-trash"></i> 삭제';
            deleteBtn.addEventListener('click', async () => {
                if (confirm(`"${item.word}"를 불용어 사전에서 삭제하시겠습니까?`)) {
                    await deleteStopword(item.word);
                }
            });
            actionCell.appendChild(deleteBtn);
            
            row.appendChild(wordCell);
            row.appendChild(categoryCell);
            row.appendChild(actionCell);
            
            stopwordsTableBody.appendChild(row);
        });
        
        // DOM 표시 로직 강화
        loadingIndicator.style.display = 'none';
        stopwordsTableContainer.style.display = 'block';
        noResults.style.display = 'none';
    }

    function updatePagination(filteredCount) {
        const paginationContainer = document.getElementById('pagination-container');
        if (!paginationContainer) {
            return;
        }
        
        totalPages = Math.ceil(filteredCount / pageSize);
        
        let paginationHTML = `
            <nav aria-label="불용어 목록 페이지네이션">
                <ul class="pagination justify-content-center">
                    <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                        <a class="page-link" href="#" data-page="${currentPage - 1}">이전</a>
                    </li>
        `;
        
        // 페이지 번호 생성
        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);
        
        if (startPage > 1) {
            paginationHTML += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="1">1</a>
                </li>
            `;
            if (startPage > 2) {
                paginationHTML += `
                    <li class="page-item disabled">
                        <a class="page-link" href="#">...</a>
                    </li>
                `;
            }
        }
        
        for (let i = startPage; i <= endPage; i++) {
            paginationHTML += `
                <li class="page-item ${i === currentPage ? 'active' : ''}">
                    <a class="page-link" href="#" data-page="${i}">${i}</a>
                </li>
            `;
        }
        
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationHTML += `
                    <li class="page-item disabled">
                        <a class="page-link" href="#">...</a>
                    </li>
                `;
            }
            paginationHTML += `
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${totalPages}">${totalPages}</a>
                </li>
            `;
        }
        
        paginationHTML += `
                    <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                        <a class="page-link" href="#" data-page="${currentPage + 1}">다음</a>
                    </li>
                </ul>
            </nav>
        `;
        
        paginationContainer.innerHTML = paginationHTML;
        
        // 페이지네이션 클릭 이벤트
        document.querySelectorAll('#pagination-container .page-link').forEach(link => {
            link.addEventListener('click', async (e) => {
                e.preventDefault();
                const page = parseInt(link.getAttribute('data-page'));
                if (page >= 1 && page <= totalPages && page !== currentPage) {
                    currentPage = page;
                    updateUI(); // No need to reload, just re-filter and re-paginate
                }
            });
        });
    }

    function showNoResults() {
        loadingIndicator.classList.add('d-none');
        stopwordsTableContainer.classList.add('d-none');
        noResults.classList.remove('d-none');
    }
    
    function updateStatistics() {
        const total = totalStopwords;
        const categories = allCategories;
        const categoryCounts = {};
        
        // 전체 데이터로 카테고리별 카운트 계산
        allStopwords.forEach(item => {
            if (!categoryCounts[item.category]) {
                categoryCounts[item.category] = 0;
            }
            categoryCounts[item.category]++;
        });
        
        // 정렬된 카테고리 목록 (지정된 순서)
        const sortedCategories = [
            '일반 불용어',
            '관사/대명사',
            '조사',
            '동사',
            '접속사',
            '형용사',
            '명사',
            '업무 관련',
            '기타'
        ];
        
        let statsHTML = `
            <div class="stat-item">
                <span class="stat-label">총 불용어 수:</span>
                <span class="stat-value">${total}</span>
            </div>
        `;
        
        // 각 카테고리별 수량 표시
        sortedCategories.forEach(category => {
            const count = categoryCounts[category] || 0;
            statsHTML += `
                <div class="stat-item">
                    <span class="stat-label">${category} 수:</span>
                    <span class="stat-value">${count}</span>
                </div>
            `;
        });
        
        statistics.innerHTML = statsHTML;
        console.log('Statistics updated:', { total, categories, categoryCounts });
    }

    function getCategories() {
        // 전체 카테고리 목록을 반환
        return allCategories;
    }

    async function classifyWord() {
        const word = newWordInput.value.trim();
        
        if (!word) {
            showToast('warning', '경고', '분류할 단어를 입력하세요.');
            return;
        }
        
        // Show classification in progress message
        const classificationStatus = document.getElementById('classification-status');
        classificationStatus.style.display = 'block';
        classificationStatus.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 자동 분류 중입니다...';
        
        try {
            const response = await fetch('/api/stopwords/classify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    word: word
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // 카테고리 선택 박스를 자동으로 선택
                categorySelect.value = data.category;
                classificationStatus.innerHTML = `<i class="fas fa-check"></i> 단어 '${word}'를 '${data.category}' 카테고리로 자동 분류했습니다.`;
                classificationStatus.style.background = '#d4edda';
                classificationStatus.style.borderColor = '#c3e6cb';
                classificationStatus.style.color = '#155724';
                
                // 3초 후 상태 메시지 숨기기
                setTimeout(() => {
                    classificationStatus.style.display = 'none';
                    classificationStatus.style.background = '#e7f3ff';
                    classificationStatus.style.borderColor = '#bee5eb';
                    classificationStatus.style.color = '#0c5460';
                }, 3000);
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            classificationStatus.innerHTML = `<i class="fas fa-exclamation-circle"></i> 분류 실패: ${error.message}`;
            classificationStatus.style.background = '#f8d7da';
            classificationStatus.style.borderColor = '#f5c6cb';
            classificationStatus.style.color = '#721c24';
            
            // 3초 후 상태 메시지 숨기기
            setTimeout(() => {
                classificationStatus.style.display = 'none';
                classificationStatus.style.background = '#e7f3ff';
                classificationStatus.style.borderColor = '#bee5eb';
                classificationStatus.style.color = '#0c5460';
            }, 3000);
        }
    }
    
    function toggleCategorySelect(isAutoClassify) {
        categorySelect.disabled = isAutoClassify;
        
        // 버튼 텍스트 변경
        autoClassifyBtn.textContent = isAutoClassify ? '자동 분류 활성화' : '수동으로 선택';
        
        // 자동 분류가 활성화된 경우, 단어 입력 시 자동으로 분류
        if (isAutoClassify && newWordInput.value.trim()) {
            classifyWord();
        }
        
        // 버튼 상태 업데이트
        if (isAutoClassify) {
            autoClassifyBtn.classList.add('btn-success');
            autoClassifyBtn.classList.remove('btn-info');
            categorySelect.style.opacity = '0.5'; // 비활성화 시 시각적으로 표시
            categorySelect.style.cursor = 'not-allowed';
        } else {
            autoClassifyBtn.classList.add('btn-info');
            autoClassifyBtn.classList.remove('btn-success');
            categorySelect.style.opacity = '1'; // 활성화 시 원래 상태로 복원
            categorySelect.style.cursor = 'pointer';
        }
    }

    async function addStopword() {
        const word = newWordInput.value.trim();
        const category = categorySelect.value;
        
        if (!word) {
            showToast('warning', '경고', '불용어를 입력하세요.');
            return;
        }
        
        if (allStopwords.some(item => item.word === word)) {
            showToast('warning', '경고', '이 단어는 이미 불용어 사전에 존재합니다.');
            return;
        }
        
        try {
            const response = await fetch('/api/stopwords', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    word: word,
                    category: category
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                allStopwords.push({ word, category });
                updateUI();
                updateStatistics();
                newWordInput.value = '';
                showToast('success', '성공', '불용어가 추가되었습니다.');
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            showToast('error', '오류', error.message);
        }
    }

    async function deleteStopword(word) {
        try {
            const response = await fetch(`/api/stopwords/${word}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                allStopwords = allStopwords.filter(item => item.word !== word);
                updateUI();
                updateStatistics();
                showToast('success', '성공', '불용어가 삭제되었습니다.');
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            showToast('error', '오류', error.message);
        }
    }

    async function searchStopwords() {
        searchTerm = searchInput.value.trim();
        updateUI();
        updateStatistics();
    }

    async function filterDemoText() {
        const text = demoTextInput.value.trim();
        
        if (!text) {
            showToast('warning', '경고', '테스트 텍스트를 입력하세요.');
            return;
        }
        
        try {
            const response = await fetch('/api/stopwords/filter', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: text
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                demoOriginal.textContent = data.original_text;
                demoFiltered.textContent = data.filtered_text;
                
                const statsHTML = `
                    <div>원본 길이: ${data.original_length}자</div>
                    <div>필터링 후 길이: ${data.filtered_length}자</div>
                    <div>제거된 단어 수: ${data.removed_count}</div>
                `;
                
                demoStats.innerHTML = statsHTML;
                demoResults.classList.remove('d-none');
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            showToast('error', '오류', error.message);
        }
    }

    function showToast(type, title, message) {
        const icon = document.getElementById('toast-icon');
        const titleEl = document.getElementById('toast-title');
        const messageEl = document.getElementById('toast-message');
        
        // Set icon and title
        switch (type) {
            case 'success':
                icon.className = 'fas fa-check-circle me-2 text-success';
                titleEl.textContent = '성공';
                titleEl.className = 'me-auto text-success';
                break;
            case 'error':
                icon.className = 'fas fa-exclamation-circle me-2 text-danger';
                titleEl.textContent = '오류';
                titleEl.className = 'me-auto text-danger';
                break;
            case 'warning':
                icon.className = 'fas fa-exclamation-triangle me-2 text-warning';
                titleEl.textContent = '경고';
                titleEl.className = 'me-auto text-warning';
                break;
            default:
                icon.className = 'fas fa-info-circle me-2 text-info';
                titleEl.textContent = '정보';
                titleEl.className = 'me-auto text-info';
        }
        
        messageEl.textContent = message;
        toast.show();
    }
    
    // 중복된 updatePagination 함수 제거 (이미 위에 정의되어 있음)

    // 페이지 크기 변경 이벤트
    const pageSizeSelect = document.getElementById('page-size-select');
    if (pageSizeSelect) {
        pageSizeSelect.addEventListener('change', function() {
            pageSize = parseInt(this.value);
            currentPage = 1; // 페이지 크기 변경 시 첫 페이지로 이동
            updateUI(); // 클라이언트에서 필터링과 페이징 처리
            updateStatistics();
            updatePagination();
        });
    }
    
    // Event listeners
    addBtn.addEventListener('click', addStopword);
    searchBtn.addEventListener('click', searchStopwords);
    demoFilterBtn.addEventListener('click', filterDemoText);
    
    // 자동 분류 버튼 이벤트
    autoClassifyBtn.addEventListener('click', function() {
        const isCurrentlyDisabled = categorySelect.disabled;
        toggleCategorySelect(!isCurrentlyDisabled);
    });
    
    // 단어 입력 시 이벤트 처리
    newWordInput.addEventListener('input', function() {
        const word = newWordInput.value.trim();
        console.log('newWordInput input event:', word);
        
        if (categorySelect.disabled && word) {
            classifyWord();
        }
    });
    
    // Enter key handlers
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchStopwords();
        }
    });
    
    newWordInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            addStopword();
        }
    });
    
    demoTextInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && e.ctrlKey) {
            filterDemoText();
        }
    });
});
