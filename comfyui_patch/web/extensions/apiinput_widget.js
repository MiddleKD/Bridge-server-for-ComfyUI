import {app} from '../scripts/app.js';

const addMenuHandler = (nodeType, cb)=> {
    const getOpts = nodeType.prototype.getExtraMenuOptions;
    nodeType.prototype.getExtraMenuOptions = function () {
        const r = getOpts.apply(this, arguments);
        cb.apply(this, arguments);
        return r;
    };
}

if (app) {
    app.registerExtension({
        name: "select custom input",
        async beforeRegisterNodeDef(nodeType, nodeData, app) {
            addMenuHandler(nodeType, function (_, options) {
                options.push({
                    content: '🧹 Custom(filter) inputs',
                    callback: (value, options, e, menu, node) => {

                        // 위젯의 이름 리스트
                        const valueList = node.widgets.map(item => item.name);

                        // node.apiinput에 저장된 기존 선택값을 배열로 변환
                        const preselectedWidgets = node.apiinput ? node.apiinput.split(",").map(item => item.trim()) : [];

                        // 모달 및 배경 생성 후 body에 추가
                        const { modal, modalOverlay } = createModalWithOverlay(node.title);

                        // 체크박스 리스트 추가
                        addCheckboxListToModal(modal, valueList, preselectedWidgets);

                        // 확인 버튼 추가 및 동작 설정
                        addConfirmButtonToModal(modal, valueList, node, modalOverlay);

                        // 닫기 버튼 추가
                        addCloseButtonToModal(modal, modalOverlay);

                        // 모달을 body에 추가하여 화면에 표시
                        document.body.appendChild(modalOverlay);
                    }
                });
            });
        }
    });
}

// 1. 모달과 배경을 함께 생성하는 함수
function createModalWithOverlay(currentTitle) {
    // 배경(모달 외부 클릭 시 닫힘)
    const modalOverlay = document.createElement("div");
    modalOverlay.style.position = "fixed";
    modalOverlay.style.top = "0";
    modalOverlay.style.left = "0";
    modalOverlay.style.width = "100%";
    modalOverlay.style.height = "100%";
    modalOverlay.style.backgroundColor = "rgba(0, 0, 0, 0.5)";
    modalOverlay.style.zIndex = "999";  // 모달 뒤에 배경이 깔리도록
    modalOverlay.style.display = "flex";
    modalOverlay.style.justifyContent = "center";
    modalOverlay.style.alignItems = "center";

    // 모달 자체 생성
    const modal = document.createElement("div");
    modal.style.backgroundColor = "#202020";
    modal.style.padding = "20px";
    modal.style.boxShadow = "0 4px 8px rgba(0, 0, 0, 0.1)";
    modal.style.borderRadius = "8px";
    modal.style.width = "300px";
    modal.style.border = "4px solid black";

    // 모달 외부 클릭 시 취소 기능으로 닫기
    modalOverlay.onclick = function (e) {
        if (e.target === modalOverlay) {
            document.body.removeChild(modalOverlay);  // 모달 닫기 (취소)
        }
    };

    // 모달 타이틀 input 추가
    const titleInputContainer = document.createElement("div");
    const titleLabel = document.createElement("label");
    titleLabel.textContent = "Title: ";
    const titleInput = document.createElement("input");
    titleInput.type = "text";
    titleInput.value = currentTitle;  // 현재 node.title을 input 기본값으로 설정
    titleInput.style.width = "100%";
    titleInput.style.marginBottom = "10px";

    titleInputContainer.appendChild(titleLabel);
    titleInputContainer.appendChild(titleInput);
    modal.appendChild(titleInputContainer);

    modalOverlay.appendChild(modal);  // 모달을 배경 안에 넣음

    return { modal, modalOverlay, titleInput };  // titleInput을 반환하여 추후 사용
}

// 2. 체크박스 리스트 추가 함수
function addCheckboxListToModal(modal, valueList, preselectedWidgets) {
    valueList.forEach((name, index) => {
        const checkboxContainer = document.createElement("div");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.id = `widget-checkbox-${index}`;
        checkbox.value = name;

        const label = document.createElement("label");
        label.htmlFor = `widget-checkbox-${index}`;
        label.textContent = name;

        // 미리 선택된 위젯은 체크 상태로 설정
        if (preselectedWidgets.includes(name)) {
            checkbox.checked = true;
        }

        checkboxContainer.appendChild(checkbox);
        checkboxContainer.appendChild(label);
        modal.appendChild(checkboxContainer);
    });
}

// 3. 확인 버튼 추가 함수 (배경도 전달하여 모달 닫기)
function addConfirmButtonToModal(modal, valueList, node, modalOverlay) {
    const confirmButton = document.createElement("button");
    confirmButton.textContent = "confirm";
    confirmButton.style.marginTop = "20px";

    confirmButton.onclick = function () {
        const selectedWidgets = [];
        valueList.forEach((name, index) => {
            const checkbox = document.getElementById(`widget-checkbox-${index}`);
            if (checkbox && checkbox.checked) {
                selectedWidgets.push(checkbox.value);
            }
        });

        // 쉼표로 구분된 문자열로 변환
        const selectedWidgetsString = selectedWidgets.join(",");

        // node.apiinput에 추가
        node.apiinput = selectedWidgetsString;

        // node.title을 모달의 titleInput 값으로 업데이트
        const titleInput = modal.querySelector("input[type='text']");
        if (titleInput) {
            node.title = titleInput.value;
        }

        // 모달 닫기
        document.body.removeChild(modalOverlay);
    };

    modal.appendChild(confirmButton);
}

// 4. 닫기 버튼 추가 함수 (배경도 전달하여 모달 닫기)
function addCloseButtonToModal(modal, modalOverlay) {
    const closeButton = document.createElement("button");
    closeButton.textContent = "close";
    closeButton.style.marginLeft = "10px";

    closeButton.onclick = function () {
        document.body.removeChild(modalOverlay);  // 모달 닫기
    };

    modal.appendChild(closeButton);
}