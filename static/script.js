document.getElementById('ask-button').addEventListener('click', function() {
    submitQuestion();
});

document.getElementById('question-input').addEventListener('keydown', function(event) {
    if (event.key === 'Enter') { // Enter 키가 눌렸을 때
        event.preventDefault(); // 기본 동작(폼 제출)을 막습니다.
        submitQuestion(); // 질문 제출 함수 호출
    }
});

document.querySelector('.google-login-btn').addEventListener('click', function() {
    // 구글 로그인 페이지로 리디렉션
    window.location.href = 'http://localhost:5000/login/google';
});

function submitQuestion() {
    const questionInput = document.getElementById('question-input');
    const questionText = questionInput.value.trim();

    if (questionText === "") return;

    // 질문을 대화창에 추가
    const conversationContainer = document.getElementById('conversation-container');
    const questionDiv = document.createElement('div');
    questionDiv.classList.add('question');
    questionDiv.textContent = `${questionText}`;
    conversationContainer.prepend(questionDiv);  // prepend를 사용하여 상단에 추가

    // AI의 답변을 대화창에 추가
    const answerDiv = document.createElement('div');
    answerDiv.classList.add('answer');
    answerDiv.textContent = `이 질문에 대한 답변을 준비중입니다.`;
    conversationContainer.prepend(answerDiv);  // prepend를 사용하여 상단에 추가

    // 입력창 비우기
    questionInput.value = "";

    // 자동으로 스크롤 하단으로 이동
    conversationContainer.scrollTop = conversationContainer.scrollHeight;

    // POST 요청 보내기
    fetch('http://localhost:5000/game', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            input: questionText
        }),
    })
    .then(response => response.json())
    .then(data => {
        // 서버에서 받은 message 필드로 AI의 답변 업데이트
        answerDiv.textContent = data.message || '답변을 받을 수 없습니다.';
    })
    .catch(error => {
        console.error('Error:', error);
        answerDiv.textContent = '서버와의 연결에 문제가 발생했습니다.';
    });
}
