import discord

class InputModal(discord.ui.Modal):
    def __init__(self, data_dict, original_view, original_interaction, callback_func, input_fields = 5,*args, **kwargs) -> None:
        self.data_dict = data_dict
        self.original_view = original_view
        self.current_stage = data_dict["current_stage"]
        self.original_interaction = original_interaction
        self.callback_func = callback_func
        super().__init__(title = "Add Players Manually",*args, **kwargs)
        for i in range(min(5,input_fields)):
            self.add_item(discord.ui.InputText(label="Player Name",
                                               required = False))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.callback_func(self, interaction)

class SelectionGenericButton(discord.ui.Button):
    def __init__(self, data_dict, callback_func, label=None, style = None, original_user_only = True, defer = True):
        if not style:
            style = discord.ButtonStyle.success
        if not label:
            label = "Button"
        self.data_dict = data_dict
        self.current_stage = data_dict["current_stage"]
        self.callback_func = callback_func
        self.original_user_only = original_user_only
        self.defer = defer
        super().__init__(
            label=label,
            style=style,
        )
    async def callback(self, interaction):
        if self.defer:
            await interaction.response.defer()
        if not self.original_user_only or interaction.user.id == self.data_dict["author"].id:
            return await self.callback_func(self, interaction, self.data_dict)

class Dropdown(discord.ui.Select):
    def __init__(self, options, title="Pick your pick", max_values = None):
        if max_values==None:
            max_values = len(options)
        self.options_data = options
        select_options = [
            discord.SelectOption(label=option) for option in options
        ]
        super().__init__(
            placeholder=title,
            min_values=1,
            max_values=max_values,
            options=select_options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class SelectView(discord.ui.View):
    def __init__(self, data_dict):
        super().__init__()
        # Adds the dropdown to our view object.
        selection_options = data_dict.get("dropdowns", {}).get(data_dict["current_stage"],{})
        if isinstance(selection_options,dict):
            ol = list(selection_options.keys())
            for sub_list in [ol[i * 5:(i + 1) * 5] for i in range(len(ol) // 5 + 1)]:
                if sub_list:
                    sub_dict = {k: selection_options[k] for k in sub_list}
                    self.add_item(Dropdown(sub_dict))
        elif isinstance(selection_options,list):
            for dropdown_manu in selection_options:
                self.add_item(Dropdown(dropdown_manu["options"], **dropdown_manu["args"]))

        # Adds the buttons to our view object.
        for button in data_dict.get("buttons",{}).get(data_dict["current_stage"], []):
            self.add_item(SelectionGenericButton(data_dict=data_dict, 
                                                 **button))

#callback functions
async def button_pressed(self, interaction, data_dict):
    self.style = discord.ButtonStyle.secondary if self.style==discord.ButtonStyle.primary else discord.ButtonStyle.primary
    msg = interaction.message
    await msg.edit(view = self.view)

async def buttons_all(self, interaction, data_dict):
    for child_interface in self.view.children:
        if isinstance(child_interface, discord.ui.Button) and child_interface.style==discord.ButtonStyle.secondary:
            child_interface.style = discord.ButtonStyle.primary
    msg = interaction.message
    await msg.edit(view = self.view)

async def selection_all(self, interaction, data_dict):
    for child_interface in self.view.children:
        if isinstance(child_interface, discord.ui.Select):
            for option in child_interface.options:
                option.default = True
                child_interface.values.append(option.value)
    msg = interaction.message
    await msg.edit(view = self.view)

async def collect_buttons_finish(self, interaction, data_dict):
    items = self.view.children
    data_dict["selections"][self.current_stage] = {child_interface.label for child_interface in self.view.children if isinstance(child_interface, discord.ui.Button) and child_interface.style == discord.ButtonStyle.primary}
    await data_dict["flow"][self.current_stage](data_dict)

async def collect_selection_finish(self, interaction, data_dict):
    items = self.view.children
    data_dict["selections"][self.current_stage] = {val: child_interface.options_data[val] for child_interface in items if isinstance(child_interface, discord.ui.Select) for val in child_interface.values}
    await data_dict["flow"][self.current_stage](data_dict)
