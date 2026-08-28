// Highlight the selected cake option as radio buttons change (progressive
// enhancement only - the form works fine without JavaScript too).
document.querySelectorAll(".cake-options").forEach((group) => {
  group.addEventListener("change", (event) => {
    if (event.target.name !== "cake_id") return;
    group.querySelectorAll(".cake-option").forEach((label) => label.classList.remove("selected"));
    event.target.closest(".cake-option")?.classList.add("selected");
  });
});
